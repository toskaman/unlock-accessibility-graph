"""Import the network layer and the lift-outage feed into Relate (idempotent MERGEs).

Graph shape (every relationship states where it comes from):

  (:NStation)-[:HAS_PLATFORM]->(:NPlatform)                      GTFS parent_station
  (:NPlatform)-[:NEXT {pattern, line, seq}]->(:NPlatform)        consecutive stops of a GTFS stopping pattern
  (:NPlatform)-[:LEG {line, patterns}]->(:NPlatform)             ride between two *boardable* platforms of one pattern
  (:NPattern)-[:OF_LINE]->(:NLine)
  (:NStation)-[:IS_ZONE]->(:TransferZone)                        same IDFM ZdC id (links to the SNCF station layer)
  (:OutageFeed)-[:LISTS]->(:LiftOutage)                          one feed snapshot, immutable
  (:LiftOutage)-[:REPORTED_AT]->(:NStation)
  (:LiftOutage)-[:AFFECTS {derivation, line_id}]->(:NPlatform)   see network/outages.py
  (:LiftOutage)-[:MATCHES_LIFT {status, score, evidence}]->(:Lift)   resolver over the SNCF station graph
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

from ..config import NORMALIZED_DIR
from ..db import GraphStore

CONSTRAINTS = [("NStation", "id"), ("NPlatform", "id"), ("NLine", "id"), ("NPattern", "id"),
               ("LiftOutage", "id"), ("OutageFeed", "id")]
BATCH = 1500

ST = [
    ("stations", """UNWIND $rows AS r MERGE (s:NStation {id: r.id})
        SET s.name = r.name, s.gtfs_id = r.gtfs_id, s.lat = r.lat, s.lon = r.lon,
            s.location = point({longitude: r.lon, latitude: r.lat}),
            s.entries_per_day = r.entries_per_day, s.entries_days = r.entries_days"""),
    ("region", """UNWIND $rows AS r MERGE (g:Region {code: r.code})
        SET g.name = r.name, g.network_label = r.network_label, g.center = r.center, g.zoom = r.zoom"""),
    ("datasets", """UNWIND $rows AS r MERGE (d:Dataset {key: r.key})
        SET d.title = r.title, d.publisher = r.publisher, d.url = r.url, d.licence = r.licence,
            d.licence_url = r.licence_url, d.sha256 = r.sha256, d.retrieved_at = r.retrieved_at, d.role = r.role"""),
    ("entries_src", """UNWIND $rows AS r MATCH (s:NStation {id: r.id}) MATCH (d:Dataset {key: r.dataset})
        MERGE (s)-[:ENTRIES_FROM]->(d)"""),
    ("lines", """UNWIND $rows AS r MERGE (l:NLine {id: r.id})
        SET l.short_name = r.short_name, l.long_name = r.long_name, l.mode = r.mode, l.color = r.color,
            l.text_color = r.text_color, l.operator = r.operator"""),
    ("platforms", """UNWIND $rows AS r MATCH (s:NStation {id: r.station_id}) MERGE (p:NPlatform {id: r.id})
        SET p.name = r.name, p.station_id = r.station_id, p.wheelchair = r.wheelchair,
            p.access_level = r.access_level, p.boardable = r.boardable, p.modes = r.modes, p.lines = r.lines,
            p.lat = r.lat, p.lon = r.lon
        MERGE (s)-[:HAS_PLATFORM]->(p)"""),
    ("patterns", """UNWIND $rows AS r MATCH (l:NLine {id: r.line_id}) MERGE (t:NPattern {id: r.id})
        SET t.line_id = r.line_id, t.direction = r.direction, t.trips = r.trips, t.headsign = r.headsign,
            t.terminus_station = r.terminus_station, t.length = r.length
        MERGE (t)-[:OF_LINE]->(l)"""),
    ("next", """UNWIND $rows AS r MATCH (a:NPlatform {id: r.a}) MATCH (b:NPlatform {id: r.b})
        MERGE (a)-[e:NEXT {pattern: r.pattern, seq: r.seq}]->(b) SET e.line = r.line"""),
    ("legs", """UNWIND $rows AS r MATCH (a:NPlatform {id: r.a}) MATCH (b:NPlatform {id: r.b})
        MERGE (a)-[e:LEG {line: r.line}]->(b) SET e.patterns = r.patterns, e.trips = r.trips, e.hops = r.hops,
            e.derivation = 'GTFS_PATTERN_BOARDABLE_ENDPOINTS'"""),
    ("zones", """UNWIND $rows AS r MATCH (s:NStation {id: r.id}) MATCH (z:TransferZone {id: r.id})
        MERGE (s)-[e:IS_ZONE]->(z) SET e.derivation = 'SAME_IDFM_ZDC_ID'"""),
]

OUT = [
    ("feed", """MERGE (f:OutageFeed {id: $feed.id})
        ON CREATE SET f.observed_at = $feed.observed_at, f.source = $feed.source, f.sha256 = $feed.sha256,
            f.feed_last_lift_update = $feed.feed_last_lift_update,
            f.feed_non_lift_last_update = $feed.feed_non_lift_last_update,
            f.lifts = $feed.lifts, f.messages = $feed.messages, f.licence = $feed.licence"""),
    ("outages", """UNWIND $rows AS r MATCH (f:OutageFeed {id: $feed.id}) MATCH (s:NStation {id: r.station_zone_id})
        MERGE (o:LiftOutage {id: r.uid})
        ON CREATE SET o.lift_key = r.id, o.operator = r.operator, o.text = r.text, o.stop_area_name = r.stop_area_name,
            o.first_reported = r.first_reported, o.last_update = r.last_update, o.announced_until = r.announced_until,
            o.messages = r.messages, o.feed_lines = r.lines, o.placement = r.placement, o.directions = r.directions,
            o.feed_id = $feed.id, o.observed_at = $feed.observed_at
        MERGE (f)-[:LISTS]->(o) MERGE (o)-[:REPORTED_AT]->(s)"""),
    ("affects", """UNWIND $rows AS r MATCH (o:LiftOutage {id: r.uid}) MATCH (p:NPlatform {id: r.platform_id})
        MERGE (o)-[e:AFFECTS {line_id: r.line_id}]->(p)
        SET e.derivation = r.derivation, e.line_derivation = r.line_derivation"""),
]


def _batches(rows, n=BATCH):
    for i in range(0, len(rows), n):
        yield rows[i:i + n]


def network_rows(net: dict) -> dict[str, list[dict]]:
    boardable = {p["id"] for p in net["platforms"] if p["boardable"]}
    nxt, legs = [], {}
    for pat in net["patterns"]:
        s = pat["stops"]
        for i in range(len(s) - 1):
            nxt.append({"a": s[i], "b": s[i + 1], "pattern": pat["id"], "seq": i, "line": pat["line_id"]})
        bs = [(i, x) for i, x in enumerate(s) if x in boardable]
        for i in range(len(bs)):
            for j in range(i + 1, len(bs)):
                (ia, a), (ib, b) = bs[i], bs[j]
                if a == b:
                    continue
                k = (a, b, pat["line_id"])
                e = legs.setdefault(k, {"a": a, "b": b, "line": k[2], "patterns": [], "trips": 0, "hops": ib - ia})
                e["patterns"].append(pat["id"])
                e["trips"] += pat["trips"]
                e["hops"] = min(e["hops"], ib - ia)
    plat = [{**p, "access_level": p.get("access_level")} for p in net["platforms"]]
    pats = [{k: v for k, v in p.items() if k != "stops"} | {"length": len(p["stops"])} for p in net["patterns"]]
    stations = [{"entries_per_day": None, "entries_days": None, **s} for s in net["stations"]]
    ds = [{k: d.get(k) for k in ("key", "title", "publisher", "url", "licence", "licence_url", "sha256", "retrieved_at", "role")}
          for d in net.get("datasets", [])]
    return {"stations": stations, "datasets": ds,
            "entries_src": [{"id": s["id"], "dataset": s.get("entries_dataset", "idfm_validations_ferre")}
                            for s in net["stations"] if s.get("entries_per_day") is not None
                            and any(d["key"] == s.get("entries_dataset", "idfm_validations_ferre") for d in ds)],
            "lines": net["lines"], "platforms": plat, "patterns": pats,
            "next": nxt, "legs": list(legs.values()),
            "region": [net["region"]] if net.get("region") else [], "zones": [{"id": s["id"]} for s in net["stations"]]}


def import_network(db: GraphStore, path: Path = NORMALIZED_DIR / "network.json") -> dict:
    net = json.loads(path.read_text(encoding="utf-8"))
    for label, prop in CONSTRAINTS:
        db.query(f"CREATE CONSTRAINT {label.lower()}_{prop} IF NOT EXISTS FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE")
    db.query("CREATE INDEX nplatform_station_idx IF NOT EXISTS FOR (n:NPlatform) ON (n.station_id)")
    rows = network_rows(net)
    for key, cypher in ST:
        for chunk in _batches(rows[key]):
            db.transaction([(cypher, {"rows": chunk})])
    return {k: len(v) for k, v in rows.items()}


def import_feed_history(db: GraphStore, path: Path = NORMALIZED_DIR / "outage_feed_history.json") -> int:
    """One (:FeedObservation) per PRIM fetch — the evidence behind "the lift messages are frozen"."""
    if not path.exists():
        return 0
    rows = json.loads(path.read_text(encoding="utf-8"))
    db.query("CREATE CONSTRAINT feedobservation_at IF NOT EXISTS FOR (n:FeedObservation) REQUIRE n.observed_at IS UNIQUE")
    db.query("""UNWIND $rows AS r MERGE (o:FeedObservation {observed_at: r.observed_at})
        SET o.lifts = r.lifts, o.messages = r.messages, o.feed_last_lift_update = r.feed_last_lift_update,
            o.feed_non_lift_last_update = r.feed_non_lift_last_update, o.lift_content_sha = r.lift_content_sha,
            o.source = 'PRIM line_reports, tag Ascenseur'""", {"rows": rows})
    return len(rows)


def import_idfm_lifts(db: GraphStore, path: Path = NORMALIZED_DIR / "idfm_lifts.json") -> dict | None:
    """IDFM « État des ascenseurs »: every lift with its status; RATP sides placed on network platforms."""
    if not path.exists():
        return None
    raw = path.read_bytes()
    doc = json.loads(raw)
    sha = hashlib.sha256(raw).hexdigest()
    feed = {"id": f"idfm_etat_ascenseurs@{sha[:12]}", "observed_at": doc.get("observed_at"), "sha256": sha,
            "lifts": doc["counts"]["lifts"], "night_closure_suspected": doc["counts"].get("night_closure_suspected", 0)}
    db.query("CREATE CONSTRAINT idfmlift_id IF NOT EXISTS FOR (n:IdfmLift) REQUIRE n.id IS UNIQUE")
    db.query("CREATE CONSTRAINT liftstatusfeed_id IF NOT EXISTS FOR (n:LiftStatusFeed) REQUIRE n.id IS UNIQUE")
    db.query("""MERGE (f:LiftStatusFeed {id: $f.id}) ON CREATE SET f.observed_at = $f.observed_at, f.sha256 = $f.sha256,
        f.lifts = $f.lifts, f.night_closure_suspected = $f.night_closure_suspected,
        f.source = 'IDFM etat-des-ascenseurs', f.licence = 'Licence Mobilités'""", {"f": feed})
    known = {r["id"] for r in db.query("MATCH (s:NStation) RETURN s.id AS id")}
    rows = [{**{k: l.get(k) for k in ("id", "operator", "zdc", "zdc_name", "status", "status_note", "raw_status",
                                      "reason", "updated", "mode", "direction", "situation", "private_id")},
             "sides_json": json.dumps(l["sides"], ensure_ascii=False)} for l in doc["lifts"] if l["zdc"] in known]
    con = [{"lift": l["id"], "platform_id": p["platform_id"], "line_id": p["line_id"], "side": s["index"],
            "derivation": s["derivation"]} for l in doc["lifts"] if l["zdc"] in known
           for s in l["sides"] if s["kind"] == "PLATFORM" for p in s.get("points", [])]
    for chunk in _batches(rows):
        db.transaction([("""UNWIND $rows AS r MATCH (f:LiftStatusFeed {id: $fid}) MATCH (s:NStation {id: r.zdc})
            MERGE (l:IdfmLift {id: r.id})
            SET l += r { .operator, .zdc_name, .status, .status_note, .raw_status, .reason, .updated, .mode, .direction, .situation, .private_id,
                         .sides_json }, l.feed_id = $fid
            MERGE (f)-[:LISTS]->(l) MERGE (l)-[:AT]->(s)""", {"rows": chunk, "fid": feed["id"]})])
    for chunk in _batches(con):
        db.transaction([("""UNWIND $rows AS r MATCH (l:IdfmLift {id: r.lift}) MATCH (p:NPlatform {id: r.platform_id})
            MERGE (l)-[e:CONNECTS {line_id: r.line_id, side: r.side}]->(p) SET e.derivation = r.derivation""",
                         {"rows": chunk})])
    same = db.query("""MATCH (l:IdfmLift {operator: 'SNCF'}) MATCH (x:Lift {id: l.id})
        MERGE (l)-[e:SAME_LIFT]->(x) SET e.derivation = 'SAME_ID' RETURN count(e) AS n""")[0]["n"]
    rep = 0
    for r in db.query("MATCH (o:LiftOutage) WHERE o.lift_key STARTS WITH 'RATP-SIRI:' RETURN o.id AS id, o.lift_key AS k"):
        key = r["k"].split(":", 1)[1]
        rep += db.query("""MATCH (o:LiftOutage {id: $o}) MATCH (l:IdfmLift) WHERE l.id CONTAINS $k
            MERGE (o)-[e:REPORTS_ON]->(l) SET e.derivation = 'SIRI_EQUIPMENT_ID' RETURN count(e) AS n""",
                        {"o": r["id"], "k": ":" + key + ":"})[0]["n"]
    hist_path = path.parent / "idfm_lift_history.json"
    obs = json.loads(hist_path.read_text(encoding="utf-8"))["observations"] if hist_path.exists() else []
    db.query("CREATE CONSTRAINT liftstatusobs_id IF NOT EXISTS FOR (n:LiftStatusObservation) REQUIRE n.id IS UNIQUE")
    for o in obs:
        db.query("""MERGE (o:LiftStatusObservation {id: $id}) SET o.observed_at = $o.observed_at, o.lifts = $o.lifts,
            o.not_available = $n, o.not_available_json = $j, o.source = 'IDFM etat-des-ascenseurs'""",
                 {"id": f"idfm_lift_status@{o['observed_at']}", "o": o, "n": len(o["not_available"]),
                  "j": json.dumps(o["not_available"], ensure_ascii=False)})
    db.query("""MATCH (o:LiftStatusObservation), (f:LiftStatusFeed {id: $fid}) WHERE o.observed_at = f.observed_at
        MERGE (f)-[:OBSERVED_AS]->(o)""", {"fid": feed["id"]})
    return {"feed_id": feed["id"], "lifts": len(rows), "connects": len(con), "same_lift": same, "reports_on": rep,
            "observations": len(obs)}


def import_outages(db: GraphStore, path: Path = NORMALIZED_DIR / "network_outages.json", resolver=None) -> dict | None:
    if not path.exists():
        return None
    raw = path.read_bytes()
    doc = json.loads(raw)
    sha = hashlib.sha256(raw).hexdigest()
    feed = {"id": f"prim_lift_outages@{sha[:12]}", "observed_at": doc["observed_at"], "source": doc.get("source"),
            "sha256": sha, "feed_last_lift_update": doc.get("feed_last_lift_update"),
            "feed_non_lift_last_update": doc.get("feed_non_lift_last_update"),
            "lifts": doc["counts"]["lifts"], "messages": doc["counts"]["messages"], "licence": "Licence Mobilités"}
    outs, aff = [], []
    known = {r["id"] for r in db.query("MATCH (s:NStation) RETURN s.id AS id")}
    for o in doc["outages"]:
        if o["station_zone_id"] not in known:
            continue
        uid = f"{feed['id']}:{o['id']}"
        outs.append({**o, "uid": uid})
        aff += [{**a, "uid": uid} for a in o["affects"]]
    db.query(OUT[0][1], {"feed": feed})
    for chunk in _batches(outs):
        db.transaction([(OUT[1][1], {"rows": chunk, "feed": feed})])
    for chunk in _batches(aff):
        db.transaction([(OUT[2][1], {"rows": chunk})])
    matched = match_sncf_lifts(db, feed["id"], resolver) if resolver is not None else None
    return {"feed_id": feed["id"], "outages": len(outs), "affects": len(aff), "matched": matched}


Q_GC_OUTAGES = """
MATCH (f:OutageFeed {id: $feed})-[:LISTS]->(o:LiftOutage {operator: 'SNCF_GC'})-[:REPORTED_AT]->(ns:NStation)
OPTIONAL MATCH (ns)-[:IS_ZONE]->(:TransferZone)<-[:IN_TRANSFER_ZONE]-(s:Station)
RETURN o.id AS id, o.text AS text, collect(DISTINCT s.id) AS stations
"""


def match_sncf_lifts(db: GraphStore, feed_id: str, ix) -> dict:
    """Read each Gares & Connexions outage message with the incident resolver, restricted to the SNCF
    stations of the same IDFM transfer zone. Only RESOLVED results become MATCHES_LIFT edges."""
    from ..engine.resolve import resolve
    rows, counts = [], defaultdict(int)
    for r in db.query(Q_GC_OUTAGES, {"feed": feed_id}):
        if not r["stations"]:
            counts["NO_SNCF_STATION"] += 1
            continue
        res = resolve(ix, r["text"], restrict_stations=r["stations"])
        counts[res["status"]] += 1
        if res["status"] == "RESOLVED":
            c = res["lift_candidates"][0]
            rows.append({"o": r["id"], "l": c["lift_id"], "score": c["score"], "evidence": c["evidence"]})
    for chunk in _batches(rows):
        db.transaction([("""UNWIND $rows AS r MATCH (o:LiftOutage {id: r.o}) MATCH (l:Lift {id: r.l})
            MERGE (o)-[e:MATCHES_LIFT]->(l) SET e.status = 'RESOLVED', e.score = r.score, e.evidence = r.evidence,
                e.derivation = 'INCIDENT_RESOLVER_SAME_ZONE'""", {"rows": chunk})])
    return dict(counts)
