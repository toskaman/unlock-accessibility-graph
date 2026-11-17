"""Export the region graphs from the Relate stores for the zero-install static demo.

    python scripts/export_static.py [out_dir]       (default: frontend/static-data)

For every built region it writes, under <out>/<code>/:
  graph.json      stations, platforms, boarding points, LEG rides, stopping patterns (geometry) and the point
                  states of each view — read from the store with Cypher (the same rows the server engine uses);
  views.json      overview, map layers, repairs, reconciliation — exactly what the API returns;
  cards.json      station cards (PRIM messages + IDFM lift list) for every station that has one;
  blockers.json   per non-open boarding point and view, the lifts/messages responsible (journey cards, alerts);
  bulletin.html   the printable bulletin.
and <out>/regions.json, <out>/compare.json, <out>/meta.json (when, from which stores, versions).

The demo loads graph.json into Relate compiled to WebAssembly in the visitor's browser and re-derives reaches
and journey legs there with Cypher; nothing in the export is invented, everything comes from the stores.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from unlock import ALGORITHM_VERSION, REGION_ALGORITHM_VERSION, __version__  # noqa: E402
from unlock.config import STORE_PATH  # noqa: E402
from unlock.db import GraphStore  # noqa: E402
from unlock.engine.service import UnlockService  # noqa: E402
from unlock.network import bulletin as B  # noqa: E402
from unlock.network.service import NetworkService  # noqa: E402
from unlock.regions import REGIONS, compare_row, paths  # noqa: E402

Q_PLATFORMS_ALL = """MATCH (s:NStation)-[:HAS_PLATFORM]->(p:NPlatform)
RETURN p.id AS id, p.name AS name, s.id AS station_id, p.lat AS lat, p.lon AS lon, p.boardable AS boardable ORDER BY id"""
Q_PATTERNS = """MATCH (t:NPattern) RETURN t.id AS id, t.line_id AS line ORDER BY id"""
Q_NEXT = """MATCH (a:NPlatform)-[r:NEXT]->(b:NPlatform) RETURN r.pattern AS pattern, r.seq AS seq, a.id AS a, b.id AS b"""
Q_LEG_PATTERN = """MATCH (a:NPlatform)-[e:LEG]->(b:NPlatform) RETURN a.id AS a, b.id AS b, e.line AS line, e.patterns[0] AS pattern"""


def _dump(path: Path, obj) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=str)
    path.write_text(text, encoding="utf-8", newline="\n")
    return len(text.encode("utf-8"))


def export_region(code: str, store: Path, out: Path) -> dict:
    with GraphStore(store, read_only=True) as db:
        ns = NetworkService(db, UnlockService(db))
        ns.region = {**ns.region, "code": code}
        net = ns.net
        st_ids = sorted(ns.stations)
        sidx = {s: i for i, s in enumerate(st_ids)}
        plats = db.query(Q_PLATFORMS_ALL)
        pidx = {p["id"]: i for i, p in enumerate(plats)}
        line_ids = sorted(ns.lines)
        lidx = {l: i for i, l in enumerate(line_ids)}
        pt_keys = sorted(net.platforms)
        kidx = {k: i for i, k in enumerate(pt_keys)}
        # stopping patterns, as platform index sequences (for drawing a leg along the track)
        seqs: dict[str, list[tuple[int, str, str]]] = {}
        for r in db.query(Q_NEXT):
            seqs.setdefault(r["pattern"], []).append((r["seq"], r["a"], r["b"]))
        pats = db.query(Q_PATTERNS)
        patidx = {p["id"]: i for i, p in enumerate(pats)}
        pattern_rows = []
        for p in pats:
            s = sorted(seqs.get(p["id"], []))
            stops = [pidx[s[0][1]]] + [pidx[x[2]] for x in s] if s else []
            pattern_rows.append([lidx.get(p["line"], -1), stops])
        leg_pat = {(r["a"], r["b"], r["line"]): patidx.get(r["pattern"], -1) for r in db.query(Q_LEG_PATTERN)}
        legs = []
        for a, b, line in net.legs:
            pa, pb = net.platforms[a]["platform_id"], net.platforms[b]["platform_id"]
            legs.append([kidx[a], kidx[b], ns.hops.get((a, b), 1), leg_pat.get((pa, pb, line), -1)])
        views = {}
        states = {}
        blockers = {}
        for v in ("best", "feed", "published"):
            ns.view_summary(v)
            stv = ns._cache[f"sum:{v}"]["_states"]
            states[v] = {str(kidx[k]): s for k, s in stv.items() if k in kidx}
            bl = {}
            for k, s in stv.items():
                if k not in kidx or s == "OPEN":
                    continue
                p = net.platforms[k]
                leg = {"board": p["platform_id"], "alight": p["platform_id"], "line": p["line"],
                       "board_state": s, "alight_state": s}
                b = ns._blocking([leg], v)
                if b:
                    bl[str(kidx[k])] = b
            blockers[v] = bl
        graph = {
            "format": "unlock-static-graph/1", "region": ns.region,
            "stations": [[s, ns.stations[s]["name"], ns.stations[s]["lat"], ns.stations[s]["lon"], ns.entries.get(s)]
                         for s in st_ids],
            "platforms": [[p["id"], p["name"], sidx[p["station_id"]], p["lat"], p["lon"]] for p in plats],
            "lines": [[l, ns.lines[l]["short_name"], ns.lines[l]["mode"], ns.lines[l]["color"], ns.lines[l]["text_color"]]
                      for l in line_ids],
            "points": [[pidx[net.platforms[k]["platform_id"]], lidx[net.platforms[k]["line"]]] for k in pt_keys],
            "legs": legs, "patterns": pattern_rows, "states": states,
            "transfer_penalty": 8,
        }
        maps = {v: ns.map_layer(v) for v in ("best", "feed", "published")}
        rank = ns.rank(40)
        rec = ns.reconciliation()
        rec_rows = []
        for r in rec["rows"][:400]:
            o = ns.outages[r["outage"]]
            lift = ns.ss.lifts.get(r.get("lift") or "")
            rec_rows.append({**r, "text": o["text"], "station": ns.stations[o["station_id"]]["name"],
                             "lift_name": lift.name if lift else None})
        missing = [{"lift": l, "name": ns.ss.lifts[l].name,
                    "station": ns.ss.stations.get(ns.ss.lifts[l].station_id, {}).get("name")} for l in rec["missing"]]
        views = {"overview": ns.overview(), "maps": maps, "rank": rank,
                 "reconciliation": {"counts": rec["counts"], "feed": ns.feed_info(), "rows": rec_rows,
                                    "missing_from_feed": missing}}
        cards = {}
        for sid in st_ids:
            outs = ns.station_outages(sid, "best")
            lifts = ns.station_lifts(sid)
            if outs or lifts:
                cards[sid] = {"outages": outs, "lifts": lifts}
        sizes = {"graph": _dump(out / code / "graph.json", graph), "views": _dump(out / code / "views.json", views),
                 "cards": _dump(out / code / "cards.json", {"lift_status_source": ns.idfm_feed, "stations": cards}),
                 "blockers": _dump(out / code / "blockers.json", blockers)}
        from unlock import history as H
        sizes["history"] = _dump(out / code / "history.json", H.region_series(code))
        sizes["history_lifts"] = _dump(out / code / "history_lifts.json", H.lift_report(ns, code))
        sizes["timelapse"] = _dump(out / code / "timelapse.json", H.region_timelapse(code))
        b = B.build(ns)
        (out / code / "bulletin.html").write_text(B.to_html(b), encoding="utf-8", newline="\n")
        (out / code / "bulletin_fr.html").write_text(B.to_html(b, "fr"), encoding="utf-8", newline="\n")
        row = compare_row(ns, code)
        info = {**ns.region, "code": code}
        return {"info": info, "compare": row, "sizes": sizes,
                "sncf_status": (ns.ss.snapshot or {}).get("observed_at"),
                "idfm_status": (ns.idfm_feed or {}).get("observed_at")}


def main(out: Path) -> None:
    stores = [("idf", Path(STORE_PATH))] + [(c, paths(c)["store"]) for c in REGIONS]
    regions, compare, status = [], [], {}
    for code, store in stores:
        if not store.exists():
            continue
        r = export_region(code, store, out)
        regions.append({**r["info"], "default": code == "idf"})
        compare.append(r["compare"])
        status[code] = {"sncf": r["sncf_status"], "idfm": r["idfm_status"]}
        print(code, r["sizes"], flush=True)
    _dump(out / "regions.json", regions)
    _dump(out / "compare.json", {"regions": compare})
    from unlock.agent.demo import load as load_agent_demo
    _dump(out / "agent_demo.json", load_agent_demo())
    _dump(out / "meta.json", {"exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                              "version": __version__, "algorithm_version": ALGORITHM_VERSION,
                              "region_algorithm_version": REGION_ALGORITHM_VERSION, "lift_status": status})


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "frontend" / "static-data")
