"""Network mode: Île-de-France step-free journeys under the lift outages that are actually reported.

Three views of the same network, each one a set of platform states (see engine.py):

* ``published`` — GTFS/IDFM boardable platforms, no outage at all (what the timetable promises);
* ``feed``      — every lift outage listed in the PRIM traffic-information feed;
* ``live``      — the best available status: SNCF's hourly lift feed for Gares & Connexions
                  lifts (evaluated on UNLOCK's station topology) + the PRIM feed for RATP lifts.

For SNCF stations the station layer turns lift states into platform reachability
(``rail_state``): that is how UNLOCK tells a lift outage with a redundant lift from one
that really cuts a platform off. Elsewhere a reported outage only removes confirmation.
"""
from __future__ import annotations

import hashlib
import json
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from .. import REGION_ALGORITHM_VERSION
from ..db import GraphStore
from ..engine import impact as I
from ..engine.model import EquipmentStatus, PairClass
from . import engine as E

A, U, K = EquipmentStatus.AVAILABLE, EquipmentStatus.UNAVAILABLE, EquipmentStatus.UNKNOWN

Q_PLATFORMS = """MATCH (s:NStation)-[:HAS_PLATFORM]->(p:NPlatform {boardable: true})
RETURN p.id AS id, s.id AS station_id, p.name AS name, p.modes AS modes, p.lines AS lines,
       p.wheelchair AS wheelchair, p.access_level AS access_level ORDER BY id"""
Q_STATIONS = """MATCH (s:NStation)
OPTIONAL MATCH (s)-[:IS_ZONE]->(:TransferZone)<-[:IN_TRANSFER_ZONE]-(x:Station)
RETURN s.id AS id, s.name AS name, s.lat AS lat, s.lon AS lon, collect(DISTINCT x.id) AS sncf ORDER BY id"""
Q_LEGS = "MATCH (a:NPlatform)-[e:LEG]->(b:NPlatform) RETURN a.id AS a, b.id AS b, e.line AS line, e.hops AS hops"
Q_LINES = "MATCH (l:NLine) RETURN l.id AS id, l.short_name AS short_name, l.mode AS mode, l.color AS color, l.text_color AS text_color, l.operator AS operator"
Q_FEED = "MATCH (f:OutageFeed) RETURN f {.*} AS f ORDER BY f.observed_at DESC LIMIT 1"
Q_OUTAGES = """MATCH (f:OutageFeed {id: $feed})-[:LISTS]->(o:LiftOutage)-[:REPORTED_AT]->(s:NStation)
OPTIONAL MATCH (o)-[a:AFFECTS]->(p:NPlatform)
OPTIONAL MATCH (o)-[m:MATCHES_LIFT]->(l:Lift)
RETURN o.id AS id, o.lift_key AS lift_key, o.operator AS operator, o.text AS text, o.first_reported AS first_reported,
       o.last_update AS last_update, o.announced_until AS announced_until, o.messages AS messages, s.id AS station_id,
       collect(DISTINCT {platform: p.id, derivation: a.derivation, line: a.line_id}) AS affects,
       collect(DISTINCT {lift: l.id, evidence: m.evidence}) AS matched ORDER BY id"""


def _days(since: str | None, now: datetime) -> int | None:
    if not since:
        return None
    return (now - datetime.fromisoformat(since).replace(tzinfo=timezone.utc)).days


class NetworkService:
    def __init__(self, db: GraphStore, station_service):
        self.db = db
        self.ss = station_service
        self.ready = False
        self.reload()

    # ------------------------------------------------------------------ load
    def reload(self) -> None:
        plats = {r["id"]: r for r in self.db.query(Q_PLATFORMS)}
        if not plats:
            self.ready = False
            return
        st_rows = self.db.query(Q_STATIONS)
        self.stations = {r["id"]: r for r in st_rows}
        self.lines = {r["id"]: r for r in self.db.query(Q_LINES)}
        # A boarding point is (platform, line): GTFS rail stations have one platform node per mode, but the
        # RER A and RER D platforms of Gare de Lyon are different places — an outage names its line.
        points = {}
        for pid, p in plats.items():
            for line in p["lines"] or []:
                if line in self.lines:
                    points[f"{pid}|{line}"] = {**p, "platform_id": pid, "line": line}
        legs, self.hops = [], {}
        for r in self.db.query(Q_LEGS):
            a, b = f"{r['a']}|{r['line']}", f"{r['b']}|{r['line']}"
            if a in points and b in points:
                legs.append((a, b, r["line"]))
                self.hops[(a, b)] = r["hops"] or 1
        self.points_of = defaultdict(list)
        for k, v in points.items():
            self.points_of[v["platform_id"]].append(k)
        self.net = E.Network(stations=self.stations, platforms=points, legs=legs, lines=self.lines)
        self.boardable_platforms = len(plats)
        feed = self.db.query(Q_FEED)
        self.feed = feed[0]["f"] if feed else None
        self.entries = {r["id"]: r["v"] for r in self.db.query(
            "MATCH (s:NStation) WHERE s.entries_per_day IS NOT NULL RETURN s.id AS id, s.entries_per_day AS v")}
        rp = self.db.query("MATCH (d:Dataset {key: 'idfm_validations_ferre'}) RETURN d.title AS title, d.url AS url, d.licence AS licence")
        self.entries_source = rp[0] if rp else None
        self.outages: dict[str, dict] = {}
        if self.feed:
            for r in self.db.query(Q_OUTAGES, {"feed": self.feed["id"]}):
                r["affects"] = sorted([a for a in r["affects"] if a["platform"]], key=lambda a: a["platform"])
                r["matched"] = [m for m in r["matched"] if m["lift"]]
                self.outages[r["id"]] = r
        # SNCF station layer per network station (rail platforms only)
        self.sncf_of = {sid: s["sncf"] for sid, s in self.stations.items() if s["sncf"]}
        self.rail_platforms = {sid: [k for k in self.net.station_platforms.get(sid, [])
                                     if self.lines[points[k]["line"]]["mode"] == "RAIL"] for sid in self.sncf_of}
        self._p_all = {sid: self._platform_anchors(sncf, {l: A for l in self.ss.lifts}) for sid, sncf in self.sncf_of.items()}
        self._cache: dict[str, Any] = {}
        self.ready = True

    # ------------------------------------------------------- station topology
    def _platform_anchors(self, sncf_ids: list[str], state) -> set[str]:
        ok = set()
        for st in sncf_ids:
            for p in self.ss.pairs_by_station.get(st, []):
                if p.kind != "PLATFORM_EXIT":
                    continue
                if I.classify(p, state).cls == PairClass.CONFIRMED_ACCESSIBLE:
                    ok.add(p.a if p.a_role != "EXIT" else p.b)
        return ok

    def rail_state(self, sid: str, state) -> str | None:
        """OPEN / DOUBT / CLOSED for the rail platform of a station that UNLOCK models in detail; None if not modelled."""
        p_all = self._p_all.get(sid)
        if not p_all:
            return None
        lost = p_all - self._platform_anchors(self.sncf_of[sid], state)
        if not lost:
            return E.OPEN
        return E.CLOSED if lost == p_all else E.DOUBT

    # ----------------------------------------------------------------- views
    def _feed_doubts(self, outage_ids, skip=frozenset()) -> dict[str, str]:
        st: dict[str, str] = {}
        for oid in outage_ids:
            if oid in skip:
                continue
            for k in self._points_hit(self.outages[oid]):
                st[k] = E.worst(st.get(k, E.OPEN), E.DOUBT)
        return st

    def _points_hit(self, o: dict) -> list[str]:
        out = []
        for a in o["affects"]:
            k = f"{a['platform']}|{a['line']}"
            out += [k] if k in self.net.platforms else list(self.points_of.get(a["platform"], []))
        return sorted(set(out))

    def view_states(self, view: str, skip_outages: frozenset = frozenset(), lift_fixes: frozenset = frozenset()) -> dict[str, str]:
        if view == "published":
            return {}
        ratp = [o for o, x in self.outages.items() if x["operator"] != "SNCF_GC"]
        gc = [o for o, x in self.outages.items() if x["operator"] == "SNCF_GC"]
        states = self._feed_doubts(ratp, skip_outages)
        if view == "feed":
            # G&C outages matched to a lift are evaluated on station topology; the rest only remove confirmation.
            down: dict[str, set[str]] = defaultdict(set)
            unmatched = []
            for o in gc:
                if o in skip_outages:
                    continue
                x = self.outages[o]
                if x["matched"] and x["station_id"] in self._p_all and self._p_all[x["station_id"]]:
                    down[x["station_id"]] |= {m["lift"] for m in x["matched"]}
                else:
                    unmatched.append(o)
            for sid, lifts in down.items():
                s = self.rail_state(sid, {**{l: A for l in self.ss.lifts}, **{l: U for l in lifts}})
                for p in self.rail_platforms.get(sid, []):
                    states[p] = E.worst(states.get(p, E.OPEN), s or E.OPEN)
            for p, s in self._feed_doubts(unmatched).items():
                states[p] = E.worst(states.get(p, E.OPEN), s)
            return states
        if view == "best":
            live = dict(self.ss.baseline_state)
            for l in lift_fixes:
                live[l] = A
            for sid in self._p_all:
                s = self.rail_state(sid, live)
                if s and s != E.OPEN:
                    for p in self.rail_platforms.get(sid, []):
                        states[p] = E.worst(states.get(p, E.OPEN), s)
            return states
        raise ValueError(view)

    def _count(self, states: dict[str, str]) -> dict[str, int]:
        conf, poss = E.usable_sets(states, self.net.platforms)
        c, per = E.reach_counts(self.net, conf)
        p, _ = E.reach_counts(self.net, poss)
        return {"confirmed": c, "possible": p, "stations_confirmed": len(per)}

    def view_summary(self, view: str) -> dict[str, Any]:
        key = f"sum:{view}"
        if key not in self._cache:
            states = self.view_states(view)
            c = self._count(states)
            sc = Counter(states.values())
            st_aff = sorted({self.net.platforms[p]["station_id"] for p, s in states.items() if s != E.OPEN})
            self._cache[key] = {"view": view, **c, "boarding_points": {"total": len(self.net.platforms),
                                "doubt": sc.get(E.DOUBT, 0), "closed": sc.get(E.CLOSED, 0)},
                                "stations_affected": len(st_aff), "_states": states}
        return {k: v for k, v in self._cache[key].items() if not k.startswith("_")}

    # --------------------------------------------------------------- outputs
    def overview(self) -> dict[str, Any]:
        if not self.ready:
            return {"available": False}
        t0 = time.time()
        views = {v: self.view_summary(v) for v in ("published", "feed", "best")}
        now = datetime.now(timezone.utc)
        ages = [_days(o["first_reported"], now) for o in self.outages.values()]
        ops = Counter(o["operator"] for o in self.outages.values())
        rec = self.reconciliation()
        return {
            "available": True, "feed": self.feed_info(now),
            "network": {"stations": len(self.stations), "stations_with_boardable_platform": len(self.net.station_platforms),
                        "boardable_platforms": self.boardable_platforms, "boarding_points": len(self.net.platforms),
                        "lines": len(self.lines),
                        "stations_with_station_topology": sum(1 for v in self._p_all.values() if v)},
            "views": views,
            "outages": {"lifts": len(self.outages), "by_operator": dict(ops),
                        "messages": sum(o["messages"] or 0 for o in self.outages.values()),
                        "older_than_30_days": sum(1 for a in ages if a is not None and a > 30),
                        "older_than_90_days": sum(1 for a in ages if a is not None and a > 90),
                        "oldest_days": max((a for a in ages if a is not None), default=None),
                        "announced_end_passed": sum(1 for o in self.outages.values()
                                                    if o["announced_until"] and o["announced_until"] < now.date().isoformat())},
            "reconciliation": rec["counts"],
            "stale_messages": self.stale_effect(),
            "computed_ms": round((time.time() - t0) * 1000), "algorithm_version": REGION_ALGORITHM_VERSION,
            "method": "Ordered station pairs joined by a step-free journey (board and alight only at boardable, usable "
                      "platforms; changes inside a station). Exact reachability over the GTFS network stored in Relate.",
        }

    def feed_info(self, now: datetime | None = None) -> dict[str, Any] | None:
        if not self.feed:
            return None
        now = now or datetime.now(timezone.utc)
        f = self.feed
        stale = _days(f.get("feed_last_lift_update"), now)
        return {"id": f["id"], "observed_at": f["observed_at"], "last_lift_update": f.get("feed_last_lift_update"),
                "last_other_update": f.get("feed_non_lift_last_update"), "lift_messages_stale_days": stale,
                "licence": f.get("licence"), "source": f.get("source")}

    def reconciliation(self) -> dict[str, Any]:
        if "rec" in self._cache:
            return self._cache["rec"]
        live = self.ss.baseline_state
        rows, counts = [], Counter()
        matched_lifts = set()
        for o in self.outages.values():
            if o["operator"] != "SNCF_GC":
                continue
            if o["matched"]:
                for m in o["matched"]:
                    matched_lifts.add(m["lift"])
                    s = live.get(m["lift"], K)
                    verdict = {A: "GHOST", U: "CONFIRMED", K: "UNCLEAR"}[s]
                    counts[verdict] += 1
                    rows.append({"outage": o["id"], "lift": m["lift"], "verdict": verdict, "sncf_state": s.value,
                                 "evidence": m["evidence"], "station_id": o["station_id"]})
            else:
                sncf = self.sncf_of.get(o["station_id"], [])
                lifts = [l for l in self.ss.lifts.values() if l.station_id in sncf]
                if lifts and all(live.get(l.id) == A for l in lifts):
                    counts["UNRESOLVED_STATION_ALL_WORKING"] += 1
                    rows.append({"outage": o["id"], "lift": None, "verdict": "UNRESOLVED_STATION_ALL_WORKING",
                                 "station_id": o["station_id"]})
                else:
                    counts["UNRESOLVED"] += 1
        in_zone = {l for sid in self.sncf_of for st in self.sncf_of[sid] for l in
                   (x.id for x in self.ss.lifts.values() if x.station_id == st)}
        missing = sorted(l for l in in_zone if live.get(l) == U and l not in matched_lifts)
        counts["MISSING_FROM_FEED"] = len(missing)
        self._cache["rec"] = {"counts": dict(counts), "rows": rows, "missing": missing}
        return self._cache["rec"]

    def stale_effect(self) -> dict[str, Any]:
        """Confirmed journeys in the feed view once every G&C message that SNCF contradicts is removed."""
        if "stale" not in self._cache:
            ghosts = frozenset(r["outage"] for r in self.reconciliation()["rows"]
                               if r["verdict"] in ("GHOST", "UNRESOLVED_STATION_ALL_WORKING"))
            states = self.view_states("feed", skip_outages=ghosts)
            c = self._count(states)
            base = self.view_summary("feed")["confirmed"]
            self._cache["stale"] = {"messages_contradicted": len(ghosts), "feed_confirmed": base,
                                    "feed_confirmed_without_them": c["confirmed"],
                                    "journeys_hidden": c["confirmed"] - base}
        return self._cache["stale"]

    def outage_view(self, oid: str) -> dict[str, Any]:
        o = self.outages[oid]
        # (entries are attached by the station card through the map layer)
        now = datetime.now(timezone.utc)
        st = self.stations[o["station_id"]]
        return {"id": oid, "lift_key": o["lift_key"], "operator": o["operator"], "text": o["text"],
                "station": {"id": st["id"], "name": st["name"], "lat": st["lat"], "lon": st["lon"]},
                "first_reported": o["first_reported"], "days_reported": _days(o["first_reported"], now),
                "last_update": o["last_update"], "announced_until": o["announced_until"], "messages": o["messages"],
                "lines": sorted({self.lines[a["line"]]["short_name"] for a in o["affects"] if a["line"] in self.lines}),
                "platforms": [{"id": a["platform"], "derivation": a["derivation"],
                               "line": self.lines.get(a["line"], {}).get("short_name")} for a in o["affects"]],
                "matched_lifts": [{"id": m["lift"], "name": self.ss.lifts[m["lift"]].name if m["lift"] in self.ss.lifts else None,
                                   "sncf_state": self.ss.baseline_state.get(m["lift"], K).value, "evidence": m["evidence"]}
                                  for m in o["matched"]],
                "sncf_station_all_working": self._station_all_working(o) if o["operator"] == "SNCF_GC" and not o["matched"] else None}

    def _station_all_working(self, o: dict) -> bool | None:
        lifts = [l for l in self.ss.lifts.values() if l.station_id in self.sncf_of.get(o["station_id"], [])]
        if not lifts:
            return None
        return all(self.ss.baseline_state.get(l.id) == A for l in lifts)

    # ---------------------------------------------------------------- ranking
    def rank(self, limit: int = 15) -> dict[str, Any]:
        """Repairs that give back the most confirmed journeys today (live view), and feed corrections
        that would stop hiding journeys (feed view)."""
        if "rank" in self._cache:
            r = self._cache["rank"]
            return {**r, "repairs": r["repairs"][:limit], "corrections": r["corrections"][:limit]}
        t0 = time.time()
        base_live = self.view_summary("best")["confirmed"]
        repairs = []
        # RATP / unknown-operator outages: remove one outage
        groups: dict[frozenset, list[str]] = defaultdict(list)
        for oid, o in self.outages.items():
            if o["operator"] != "SNCF_GC":
                groups[frozenset(self._points_hit(o))].append(oid)
        memo: dict[Any, int] = {}
        for oid, o in sorted(self.outages.items()):
            if o["operator"] == "SNCF_GC":
                continue
            states = self.view_states("best", skip_outages=frozenset([oid]))
            key = ("live-skip", frozenset(states.items()))
            if key not in memo:
                memo[key] = E.reach_counts(self.net, E.usable_sets(states, self.net.platforms)[0])[0]
            gain = memo[key] - base_live
            if gain > 0:
                repairs.append({"kind": "RATP_FEED_OUTAGE", "outage": oid, "gain": gain, **self._label_outage(oid)})
        # SNCF lifts not available in the hourly feed
        for lid, s in sorted(self.ss.baseline_state.items()):
            if s == A:
                continue
            states = self.view_states("best", lift_fixes=frozenset([lid]))
            key = ("live-fix", frozenset(states.items()))
            if key not in memo:
                memo[key] = E.reach_counts(self.net, E.usable_sets(states, self.net.platforms)[0])[0]
            gain = memo[key] - base_live
            if gain > 0:
                l = self.ss.lifts[lid]
                st = self.ss.stations.get(l.station_id, {})
                repairs.append({"kind": "SNCF_LIFT", "lift": lid, "gain": gain, "name": l.name, "state": s.value,
                                "station": st.get("name"), "station_id": l.station_id})
        repairs.sort(key=lambda r: (-r["gain"], r.get("station") or "", r.get("outage") or r.get("lift")))
        # corrections: ghost G&C outages in the feed view
        base_feed = self.view_summary("feed")["confirmed"]
        corrections = []
        for row in self.reconciliation()["rows"]:
            if row["verdict"] not in ("GHOST", "UNRESOLVED_STATION_ALL_WORKING"):
                continue
            states = self.view_states("feed", skip_outages=frozenset([row["outage"]]))
            key = ("feed-skip", frozenset(states.items()))
            if key not in memo:
                memo[key] = E.reach_counts(self.net, E.usable_sets(states, self.net.platforms)[0])[0]
            gain = memo[key] - base_feed
            corrections.append({"outage": row["outage"], "verdict": row["verdict"], "gain": gain,
                                **self._label_outage(row["outage"])})
        corrections.sort(key=lambda r: (-r["gain"], r["station"], r["outage"]))
        res = {"base_live_confirmed": base_live, "base_feed_confirmed": base_feed, "repairs": repairs,
               "corrections": corrections, "evaluations": len(memo), "computed_ms": round((time.time() - t0) * 1000),
               "method": "Each candidate is evaluated alone against the same view; gain = additional confirmed "
                         "ordered station pairs. Deterministic order: gain, station name, id."}
        self._cache["rank"] = res
        return {**res, "repairs": repairs[:limit], "corrections": corrections[:limit]}

    def warm(self) -> None:
        """Pre-compute the expensive region tables (pure Python, no store access)."""
        if not self.ready:
            return
        for v in ("published", "feed", "best"):
            self.view_summary(v)
        self.rank(1)

    def _label_outage(self, oid: str) -> dict[str, Any]:
        o = self.outages[oid]
        st = self.stations[o["station_id"]]
        return {"station": st["name"], "station_id": o["station_id"], "text": o["text"], "operator": o["operator"],
                "first_reported": o["first_reported"],
                "lines": sorted({self.lines[a["line"]]["short_name"] for a in o["affects"] if a["line"] in self.lines})}

    # --------------------------------------------------------------- journeys
    def station_search(self, q: str, limit: int = 8) -> list[dict]:
        from ..ingest.spaces import normalize
        n = normalize(q or "").strip()
        if not n:
            return []
        out = []
        for sid, s in self.stations.items():
            nm = normalize(s["name"])
            if n in nm:
                out.append((0 if nm.startswith(n) else 1, len(nm), s["name"], sid))
        out.sort()
        return [{"id": sid, "name": name, "boardable": sid in self.net.station_platforms} for _, _, name, sid in out[:limit]]

    def check_journey(self, a: str, b: str, view: str = "best") -> dict[str, Any]:
        if a not in self.stations or b not in self.stations:
            raise KeyError("unknown station")
        self.view_summary(view)
        states = self._cache[f"sum:{view}"]["_states"]
        conf, poss = E.usable_sets(states, self.net.platforms)
        allp = set(self.net.platforms)
        res = {"from": self._st(a), "to": self._st(b), "view": view}
        for label, usable in (("confirmed", conf), ("possible", poss), ("published", allp)):
            legs = E.journey(self.net, usable, a, b, self.hops)
            if legs is not None:
                res["verdict"] = {"confirmed": "STEP_FREE", "possible": "STEP_FREE_IF_LIFTS_WORK",
                                  "published": "CUT_BY_OUTAGES"}[label]
                res["legs"] = [self._leg(l, states) for l in legs]
                break
        else:
            res["verdict"] = "NO_STEP_FREE_ROUTE_PUBLISHED"
            res["legs"] = []
            res["reason"] = self._why_none(a, b)
        if res["verdict"] != "STEP_FREE" and res["legs"]:
            res["blocking_outages"] = self._blocking(res["legs"], view)
        res["verification"] = self.verify_legs(res["legs"])
        for l in res["legs"]:
            l["path"] = self.leg_path(l)
        return res

    def leg_path(self, leg: dict) -> list[list[float]]:
        """Coordinates of the stops ridden on one leg, read from the NEXT chain of one of its patterns."""
        rows = self.db.query("""MATCH (:NPlatform {id: $a})-[e:LEG {line: $line}]->(:NPlatform {id: $b})
            WITH e.patterns[0] AS pat
            MATCH (x:NPlatform)-[r:NEXT {pattern: pat}]->(y:NPlatform)
            RETURN r.seq AS seq, x.id AS x, x.lon AS xlon, x.lat AS xlat, y.id AS y, y.lon AS ylon, y.lat AS ylat
            ORDER BY seq""", {"a": leg["board"], "b": leg["alight"], "line": leg["line"]})
        coords, on = [], False
        for r in rows:
            if r["x"] == leg["board"]:
                on = True
                coords = [[r["xlon"], r["xlat"]]]
            if on:
                coords.append([r["ylon"], r["ylat"]])
                if r["y"] == leg["alight"]:
                    break
        return coords

    def _why_none(self, a, b) -> str:
        if a not in self.net.station_platforms:
            return f"{self.stations[a]['name']} has no platform declared wheelchair-boardable in GTFS/IDFM data."
        if b not in self.net.station_platforms:
            return f"{self.stations[b]['name']} has no platform declared wheelchair-boardable in GTFS/IDFM data."
        return "The two stations are not connected by boardable platforms in the published network."

    def _st(self, sid):
        s = self.stations[sid]
        return {"id": sid, "name": s["name"], "lat": s["lat"], "lon": s["lon"]}

    def _leg(self, l, states):
        line = self.lines.get(l["line"], {})
        pb, pa = self.net.platforms[l["board"]], self.net.platforms[l["alight"]]
        return {**l, "board": pb["platform_id"], "alight": pa["platform_id"],
                "board_name": pb["name"], "alight_name": pa["name"],
                "line_name": line.get("short_name"), "mode": line.get("mode"), "color": line.get("color"),
                "text_color": line.get("text_color"),
                "from_name": self.stations[l["from"]]["name"], "to_name": self.stations[l["to"]]["name"],
                "board_state": states.get(l["board"], E.OPEN), "alight_state": states.get(l["alight"], E.OPEN)}

    def _blocking(self, legs, view) -> list[dict]:
        pts = {(l["board"], l["line"]) for l in legs} | {(l["alight"], l["line"]) for l in legs}
        out = []
        for oid, o in sorted(self.outages.items()):
            if view == "best" and o["operator"] == "SNCF_GC":
                continue
            if view == "published":
                break
            if any((a["platform"], a["line"]) in pts for a in o["affects"]):
                out.append({"outage": oid, **self._label_outage(oid)})
        if view == "best":
            for l in legs:
                for pid in (l["board"], l["alight"]):
                    sid = self.net.platforms[f"{pid}|{l['line']}"]["station_id"]
                    for st in self.sncf_of.get(sid, []):
                        for lift in self.ss.lifts.values():
                            if lift.station_id == st and self.ss.baseline_state.get(lift.id) != A and \
                                    l.get(f"{'board' if pid == l['board'] else 'alight'}_state", E.OPEN) != E.OPEN:
                                out.append({"lift": lift.id, "name": lift.name, "station": self.stations[sid]["name"],
                                            "state": self.ss.baseline_state[lift.id].value, "operator": "SNCF_GC"})
        seen, uniq = set(), []
        for x in out:
            k = x.get("outage") or x.get("lift")
            if k not in seen:
                seen.add(k)
                uniq.append(x)
        return uniq

    def verify_legs(self, legs: list[dict]) -> dict[str, Any]:
        """Re-check every leg in Relate: both platforms exist, are boardable, belong to the stated stations,
        and a LEG relationship of that line joins them."""
        if not legs:
            return {"legs": 0, "verified": 0, "ok": True}
        rows = self.db.query("""UNWIND $legs AS l
            MATCH (s1:NStation {id: l.from})-[:HAS_PLATFORM]->(x:NPlatform {id: l.board, boardable: true})
                  -[e:LEG {line: l.line}]->(y:NPlatform {id: l.alight, boardable: true})<-[:HAS_PLATFORM]-(s2:NStation {id: l.to})
            RETURN count(e) AS n""", {"legs": [{k: l[k] for k in ("from", "to", "board", "alight", "line")} for l in legs]})
        n = rows[0]["n"] if rows else 0
        return {"legs": len(legs), "verified": n, "ok": n == len(legs),
                "query": "MATCH (s1:NStation)-[:HAS_PLATFORM]->(x:NPlatform {boardable:true})-[e:LEG {line}]->(y)<-[:HAS_PLATFORM]-(s2)"}

    # ------------------------------------------------------------------ reach
    Q_REACH_STEP = """UNWIND $frontier AS sid
MATCH (s:NStation {id: sid})-[:HAS_PLATFORM]->(x:NPlatform)-[e:LEG]->(y:NPlatform)<-[:HAS_PLATFORM]-(t:NStation)
WHERE (x.id + '|' + e.line) IN $usable AND (y.id + '|' + e.line) IN $usable
RETURN DISTINCT t.id AS id"""

    def cypher_reach(self, origin: str, usable: set[str]) -> tuple[set[str], int]:
        """Independent re-derivation in Relate: breadth-first, one Cypher query per round over HAS_PLATFORM/LEG,
        restricted to the usable boarding points. Returns (stations, rounds)."""
        seen, frontier, rounds = {origin}, [origin], 0
        u = sorted(usable)
        while frontier:
            rows = self.db.query(self.Q_REACH_STEP, {"frontier": frontier, "usable": u})
            rounds += 1
            frontier = sorted({r["id"] for r in rows} - seen)
            seen |= set(frontier)
        seen.discard(origin)
        return seen, rounds

    def reach(self, origin: str, view: str = "best", verify: bool = True) -> dict[str, Any]:
        """Where can a wheelchair user go from ``origin``? Every station is classed CONFIRMED / IF_LIFTS_WORK
        (needs a platform whose listed lift outage may or may not matter) / CUT (reachable in the published
        network, not any more) / UNREACHABLE (no published step-free route) / NOT_BOARDABLE."""
        if origin not in self.stations:
            raise KeyError(origin)
        self.view_summary(view)
        states = self._cache[f"sum:{view}"]["_states"]
        conf, poss = E.usable_sets(states, self.net.platforms)
        c = E.reach_set(self.net, conf, origin)
        p = E.reach_set(self.net, poss, origin) - c
        pub = E.reach_set(self.net, set(self.net.platforms), origin)
        cut = pub - c - p
        classes = {}
        for sid in self.stations:
            if sid == origin:
                continue
            classes[sid] = ("CONFIRMED" if sid in c else "IF_LIFTS_WORK" if sid in p else "CUT" if sid in cut
                            else "UNREACHABLE" if sid in self.net.station_platforms else "NOT_BOARDABLE")
        ent = lambda ids: sum(self.entries.get(i, 0) for i in ids)
        res = {"origin": self._st(origin), "view": view, "classes": classes,
               "counts": {"confirmed": len(c), "if_lifts_work": len(p), "cut": len(cut), "published": len(pub)},
               "entries_per_day": {"confirmed": round(ent(c)), "if_lifts_work": round(ent(p)), "cut": round(ent(cut))},
               "origin_boardable": origin in self.net.station_platforms}
        if verify:
            t0 = time.time()
            cy, rounds = self.cypher_reach(origin, conf)
            res["verification"] = {"engine": len(c), "cypher": len(cy), "ok": cy == c, "rounds": rounds,
                                   "ms": round((time.time() - t0) * 1000),
                                   "query": "UNWIND $frontier … (s)-[:HAS_PLATFORM]->(x)-[e:LEG]->(y)<-[:HAS_PLATFORM]-(t), "
                                            "x and y usable — repeated until no new station"}
        return res

    # ------------------------------------------------------------------- map
    def map_layer(self, view: str = "best") -> dict[str, Any]:
        self.view_summary(view)
        states = self._cache[f"sum:{view}"]["_states"]
        by_station: dict[str, list[str]] = defaultdict(list)
        for p, s in states.items():
            by_station[self.net.platforms[p]["station_id"]].append(s)
        n_out = Counter(o["station_id"] for o in self.outages.values()
                        if not (view == "best" and o["operator"] == "SNCF_GC"))
        feats = []
        for sid, s in sorted(self.stations.items()):
            if sid in self.net.station_platforms:
                ss = by_station.get(sid, [])
                state = E.CLOSED if E.CLOSED in ss else (E.DOUBT if ss else E.OPEN)
            else:
                state = "NOT_BOARDABLE"
            feats.append({"id": sid, "name": s["name"], "lat": s["lat"], "lon": s["lon"], "state": state,
                          "entries_per_day": self.entries.get(sid),
                          "outages": n_out.get(sid, 0), "detail": bool(self._p_all.get(sid)),
                          "sncf_station": (self.sncf_of.get(sid) or [None])[0]})
        return {"view": view, "stations": feats}

    def station_outages(self, sid: str, view: str = "best") -> list[dict]:
        """Every lift outage the PRIM feed lists at this station (the UI says which ones the view ignores)."""
        return [self.outage_view(oid) for oid, o in sorted(self.outages.items()) if o["station_id"] == sid]

    def fingerprint(self) -> str:
        return hashlib.sha256(json.dumps([self.feed and self.feed["id"], self.ss.snapshot["id"], len(self.net.legs)]).encode()).hexdigest()[:12]
