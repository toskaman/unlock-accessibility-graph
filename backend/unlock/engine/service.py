"""Application service: scenarios, analyses, rankings and evidence over Relate.

The service caches the graph-derived route structure (which lifts each
modeled pair needs) after loading it from Relate with one Cypher traversal;
scenario state, results and provenance are persisted back into Relate.
The baseline status observations are never modified.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from .. import ALGORITHM_VERSION
from ..db import GraphStore
from . import graph as G
from . import impact as I
from .model import EquipmentStatus, Pair, PairClass

E = EquipmentStatus


class NotFound(LookupError):
    pass


class InvalidScenario(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class UnlockService:
    def __init__(self, db: GraphStore):
        self.db = db
        self.reload()

    # ------------------------------------------------------------------ load
    def reload(self) -> None:
        snap = G.latest_snapshot(self.db)
        if not snap:
            raise RuntimeError("The Relate store holds no status snapshot — run the import first.")
        self.snapshot = snap
        self.pairs: list[Pair] = G.load_pairs(self.db)
        self.pairs_by_id = {p.id: p for p in self.pairs}
        self.pairs_by_station: dict[str, list[Pair]] = defaultdict(list)
        for p in self.pairs:
            self.pairs_by_station[p.station_id].append(p)
        self.lifts = G.load_lifts(self.db, snap["id"])
        self.baseline_state = I.effective_state(self.lifts, {})
        self.baseline = I.evaluate(self.pairs, self.baseline_state)
        self.pairs_hash = hashlib.sha256(json.dumps(
            [(p.id, p.a_assertion.value, p.b_assertion.value, [r.lifts for r in p.routes]) for p in self.pairs]
        ).encode()).hexdigest()[:16]
        rows = self.db.query("""
            MATCH (s:Station)
            OPTIONAL MATCH (s)-[:IN_TRANSFER_ZONE]->(z:TransferZone)
            OPTIONAL MATCH (z)-[:SERVED_BY]->(n:Line)
            RETURN s.id AS id, s.name AS name, s.lon AS lon, s.lat AS lat, z.id AS zone_id, z.name AS zone_name,
                   collect(DISTINCT n {.id, .short_name, .mode, .color, .text_color}) AS lines
            ORDER BY id""")
        self.stations = {r["id"]: r for r in rows}
        self.space_names = {r["id"]: r for r in self.db.query(
            "MATCH (s:Station)-[:HAS_SPACE]->(sp:Space) RETURN sp.id AS id, sp.name AS name, sp.role AS role, s.id AS station")}

    # ----------------------------------------------------------- read models
    def freshness(self) -> dict[str, Any]:
        f, hours = I.freshness(self.snapshot.get("observed_at"))
        return {"snapshot_id": self.snapshot["id"], "observed_at": self.snapshot.get("observed_at"),
                "freshness": f.value, "age_hours": round(hours, 2) if hours is not None else None}

    def summary(self) -> dict[str, Any]:
        lifts_state = Counter(s.value for s in self.baseline_state.values())
        counts = self.db.counts()
        datasets = self.db.query("""MATCH (d:Dataset) RETURN d.key AS key, d.title AS title, d.publisher AS publisher,
            d.licence AS licence, d.sha256 AS sha256, d.retrieved_at AS retrieved_at,
            d.publisher_modified AS publisher_modified, d.url AS url ORDER BY key""")
        modeled = sum(1 for p in self.pairs if p.routes)
        return {
            "algorithm_version": ALGORITHM_VERSION, "store": str(self.db.path),
            "graph": counts, "datasets": datasets, "status": self.freshness(),
            "stations": len(self.stations), "lifts": len(self.lifts), "lift_states": dict(lifts_state),
            "pairs": self.baseline.counts, "pairs_with_modeled_route": modeled,
            "coverage": {"numerator": modeled, "denominator": len(self.pairs),
                         "ratio": round(modeled / len(self.pairs), 4) if self.pairs else None},
        }

    def station_list(self) -> list[dict[str, Any]]:
        lifts_by_station: dict[str, list[str]] = defaultdict(list)
        for l in self.lifts.values():
            lifts_by_station[l.station_id].append(l.id)
        out = []
        for sid, s in self.stations.items():
            pids = [p.id for p in self.pairs_by_station.get(sid, [])]
            c = Counter(self.baseline.results[p].cls.value for p in pids)
            states = Counter(self.baseline_state[l].value for l in lifts_by_station.get(sid, []))
            out.append({"id": sid, "name": s["name"], "lon": s["lon"], "lat": s["lat"],
                        "lines": s["lines"], "lifts": len(lifts_by_station.get(sid, [])), "lift_states": dict(states),
                        "pairs": len(pids), "confirmed": c.get("CONFIRMED_ACCESSIBLE", 0),
                        "blocked": c.get("CONFIRMED_BLOCKED", 0), "unverified": c.get("UNVERIFIED", 0),
                        "out_of_scope": c.get("OUT_OF_SCOPE", 0)})
        return out

    def station_graph(self, station_id: str, scenario_id: str | None = None) -> dict[str, Any]:
        if station_id not in self.stations:
            raise NotFound(station_id)
        rows = self.db.query("""
            MATCH (s:Station {id: $id})
            OPTIONAL MATCH (s)-[:HAS_SPACE]->(sp:Space)
            OPTIONAL MATCH (sp)-[:IS_PLATFORM_OF]->(q:Quay)<-[:ABOUT]-(a:AccessibilityAssertion)
            RETURN sp.id AS id, sp.name AS name, sp.role AS role, q.id AS quay_id, q.name AS quay_name,
                   a.value AS step_free ORDER BY id""", {"id": station_id})
        spaces = [r for r in rows if r["id"]]
        edges = self.db.query("""
            MATCH (s:Station {id: $id})-[:HAS_LIFT]->(l:Lift)-[e:SERVES]->(sp:Space)
            RETURN l.id AS lift, sp.id AS space, e.derivation AS derivation, e.side_text AS side_text
            ORDER BY lift, space""", {"id": station_id})
        state, scenario = self._scenario_state(scenario_id)
        lifts = [{"id": l.id, "name": l.name, "description": l.description, "baseline": l.baseline.value,
                  "raw_state": l.raw_state, "state": state[l.id].value,
                  "overridden": l.id in scenario.get("overrides", {})}
                 for l in sorted(self.lifts.values(), key=lambda x: x.id) if l.station_id == station_id]
        local = self.pairs_by_station.get(station_id, [])
        ev = I.evaluate(local, state)
        base = I.evaluate(local, self.baseline_state)
        pairs = [self._pair_view(p, ev.results[p.id], base.results[p.id]) for p in local]
        s = self.stations[station_id]
        return {"station": {"id": station_id, "name": s["name"], "lon": s["lon"], "lat": s["lat"],
                            "zone": {"id": s["zone_id"], "name": s["zone_name"]}, "lines": s["lines"]},
                "spaces": spaces, "lifts": lifts, "serves": edges, "pairs": pairs,
                "counts": ev.counts, "baseline_counts": base.counts, "scenario_id": scenario_id}

    def _pair_view(self, p: Pair, r, base) -> dict[str, Any]:
        return {"id": p.id, "a": p.a, "b": p.b, "a_name": self.space_names[p.a]["name"], "b_name": self.space_names[p.b]["name"],
                "a_role": p.a_role, "b_role": p.b_role, "kind": p.kind,
                "a_assertion": p.a_assertion.value, "b_assertion": p.b_assertion.value,
                "routes": [{"lifts": list(rt.lifts), "nodes": list(rt.nodes), "state": st.value}
                           for rt, st in zip(p.routes, r.route_states)],
                "cls": r.cls.value, "reason": r.reason.value, "baseline_cls": base.cls.value,
                "blocking_lifts": list(r.blocking_lifts), "unknown_lifts": list(r.unknown_lifts)}

    # -------------------------------------------------------------- scenarios
    def _validate_overrides(self, overrides: dict[str, str]) -> dict[str, EquipmentStatus]:
        if not overrides:
            raise InvalidScenario("A scenario needs at least one lift override.")
        if len(overrides) > 50:
            raise InvalidScenario("At most 50 overrides per scenario.")
        out = {}
        for lid, st in overrides.items():
            if lid not in self.lifts:
                raise InvalidScenario(f"Unknown lift id: {lid!r}")
            try:
                out[lid] = EquipmentStatus(st)
            except ValueError:
                raise InvalidScenario(f"Invalid state {st!r}; expected AVAILABLE, UNAVAILABLE or UNKNOWN") from None
        return out

    def create_scenario(self, name: str, overrides: dict[str, str], kind: str = "SIMULATED_OUTAGE") -> dict[str, Any]:
        ov = self._validate_overrides(overrides)
        sid = "scn-" + uuid.uuid4().hex[:12]
        stmts = [("""MERGE (s:Scenario {id: $id})
                     SET s.name = $name, s.kind = $kind, s.created_at = $at, s.base_snapshot_id = $snap,
                         s.algorithm_version = $alg, s.simulated = true""",
                  {"id": sid, "name": name[:120], "kind": kind, "at": _now(), "snap": self.snapshot["id"], "alg": ALGORITHM_VERSION}),
                 ("""MATCH (s:Scenario {id: $id}) MATCH (d:Dataset {key: 'sncf_lift_status'})
                     MERGE (s)-[:BASED_ON {snapshot_id: $snap}]->(d)""", {"id": sid, "snap": self.snapshot["id"]}),
                 ("""MATCH (s:Scenario {id: $id}) UNWIND $ov AS o MATCH (l:Lift {id: o.lift})
                     MERGE (s)-[r:OVERRIDES]->(l) SET r.state = o.state""",
                  {"id": sid, "ov": [{"lift": k, "state": v.value} for k, v in sorted(ov.items())]})]
        self.db.transaction(stmts)
        return self.get_scenario(sid)

    def update_overrides(self, scenario_id: str, overrides: dict[str, str]) -> dict[str, Any]:
        self.get_scenario(scenario_id)
        ov = self._validate_overrides(overrides)
        self.db.transaction([
            ("MATCH (s:Scenario {id: $id})-[r:OVERRIDES]->() DELETE r", {"id": scenario_id}),
            ("""MATCH (s:Scenario {id: $id}) UNWIND $ov AS o MATCH (l:Lift {id: o.lift})
                MERGE (s)-[r:OVERRIDES]->(l) SET r.state = o.state""",
             {"id": scenario_id, "ov": [{"lift": k, "state": v.value} for k, v in sorted(ov.items())]}),
        ])
        return self.get_scenario(scenario_id)

    def get_scenario(self, scenario_id: str) -> dict[str, Any]:
        rows = self.db.query("""MATCH (s:Scenario {id: $id})
            OPTIONAL MATCH (s)-[r:OVERRIDES]->(l:Lift)
            RETURN s {.*} AS scenario, collect({lift: l.id, state: r.state}) AS overrides""", {"id": scenario_id})
        if not rows or rows[0]["scenario"] is None:
            raise NotFound(scenario_id)
        sc = rows[0]["scenario"]
        sc["overrides"] = {o["lift"]: o["state"] for o in rows[0]["overrides"] if o["lift"]}
        return sc

    def list_scenarios(self) -> list[dict[str, Any]]:
        rows = self.db.query("""MATCH (s:Scenario) OPTIONAL MATCH (s)-[r:OVERRIDES]->(l:Lift)
            RETURN s {.*} AS scenario, count(r) AS n ORDER BY s.created_at DESC LIMIT 100""")
        return [dict(r["scenario"], override_count=r["n"]) for r in rows]

    def delete_scenario(self, scenario_id: str) -> None:
        self.get_scenario(scenario_id)
        self.db.transaction([("""MATCH (s:Scenario {id: $id})
            OPTIONAL MATCH (s)-[:PRODUCES]->(a:AnalysisResult)
            DETACH DELETE s, a""", {"id": scenario_id})])

    def _scenario_state(self, scenario_id: str | None) -> tuple[dict[str, EquipmentStatus], dict[str, Any]]:
        if not scenario_id:
            return dict(self.baseline_state), {"overrides": {}}
        sc = self.get_scenario(scenario_id)
        if sc.get("base_snapshot_id") != self.snapshot["id"]:
            raise InvalidScenario(f"Scenario {scenario_id} was built on snapshot {sc.get('base_snapshot_id')}, "
                                  f"not the loaded snapshot {self.snapshot['id']}")
        ov = {k: E(v) for k, v in sc["overrides"].items()}
        return I.effective_state(self.lifts, ov), sc

    # --------------------------------------------------------------- analysis
    def analyze(self, scenario_id: str) -> dict[str, Any]:
        state, sc = self._scenario_state(scenario_id)
        ev = I.evaluate(self.pairs, state)
        d = I.diff(self.baseline, ev)
        lost = sorted(self.baseline.confirmed() - ev.confirmed())
        gained = sorted(ev.confirmed() - self.baseline.confirmed())
        input_hash = hashlib.sha256(json.dumps({
            "snapshot": self.snapshot["id"], "overrides": sorted(sc["overrides"].items()),
            "alg": ALGORITHM_VERSION, "pairs": self.pairs_hash}, sort_keys=True).encode()).hexdigest()[:16]
        analysis_id = f"ana-{input_hash}"
        affected_stations = sorted({self.pairs_by_id[p].station_id for p in lost + gained} |
                                   {self.lifts[l].station_id for l in sc["overrides"]})
        result = {
            "analysis_id": analysis_id, "scenario_id": scenario_id, "scenario_name": sc.get("name"),
            "algorithm_version": ALGORITHM_VERSION, "snapshot": self.freshness(), "input_hash": input_hash,
            "overrides": sc["overrides"],
            "baseline_counts": self.baseline.counts, "scenario_counts": ev.counts,
            "lost_confirmed": lost, "gained_confirmed": gained, "transitions": {k: len(v) for k, v in d.items()},
            "transition_pairs": d, "affected_stations": affected_stations,
            "lost_by_station": dict(Counter(self.pairs_by_id[p].station_id for p in lost)),
        }
        self.db.transaction([("""MATCH (s:Scenario {id: $sid})
            MERGE (a:AnalysisResult {id: $aid})
            ON CREATE SET a.created_at = $at
            SET a.algorithm_version = $alg, a.snapshot_id = $snap, a.input_hash = $h, a.pairs_hash = $ph,
                a.baseline_confirmed = $bc, a.scenario_confirmed = $sc, a.lost = $lost, a.gained = $gained,
                a.summary_json = $json
            MERGE (s)-[:PRODUCES]->(a)""", {
            "sid": scenario_id, "aid": analysis_id, "at": _now(), "alg": ALGORITHM_VERSION,
            "snap": self.snapshot["id"], "h": input_hash, "ph": self.pairs_hash,
            "bc": self.baseline.counts["CONFIRMED_ACCESSIBLE"], "sc": ev.counts["CONFIRMED_ACCESSIBLE"],
            "lost": len(lost), "gained": len(gained),
            "json": json.dumps({k: result[k] for k in ("baseline_counts", "scenario_counts", "transitions", "overrides")}, sort_keys=True)})])
        return result

    def rank(self, scenario_id: str | None, limit: int = 25) -> dict[str, Any]:
        state, sc = self._scenario_state(scenario_id)
        cands = I.rank_interventions(self.pairs, self.lifts, state)
        ev = I.evaluate(self.pairs, state)
        out = []
        for i, c in enumerate(cands[:limit]):
            l = self.lifts[c.lift_id]
            reason = (f"Restoring this lift makes {c.gain} modeled pair(s) confirmed step-free"
                      if c.gain > 0 else
                      ("No gain on its own: the pairs that depend on it are also blocked by "
                       f"{len(c.still_blocked_by_others)} other lift(s)" if c.still_blocked_by_others else
                       "No gain: dependent pairs remain unverified or blocked for other reasons"))
            out.append({
                "rank": i + 1, "lift_id": c.lift_id, "lift_name": l.name, "description": l.description,
                "station_id": c.station_id, "station_name": self.stations[c.station_id]["name"],
                "current_state": c.current_state.value, "baseline_state": l.baseline.value,
                "simulated": c.lift_id in sc.get("overrides", {}),
                "gain": c.gain, "restored_pairs": c.restored_pairs, "resolved_unverified": c.resolved_unverified,
                "pairs_depending": c.pairs_depending, "still_blocked_by_others": c.still_blocked_by_others,
                "reason": reason})
        return {"scenario_id": scenario_id, "snapshot": self.freshness(), "algorithm_version": ALGORITHM_VERSION,
                "confirmed_now": ev.counts["CONFIRMED_ACCESSIBLE"], "candidates": out, "candidate_count": len(cands),
                "metric": "Δ confirmed step-free origin–destination pairs (modeled pairs, not people)"}

    def plan(self, scenario_id: str | None, budget: int) -> dict[str, Any]:
        if not 1 <= budget <= 5:
            raise InvalidScenario("budget must be between 1 and 5")
        state, _ = self._scenario_state(scenario_id)
        p = I.best_plan(self.pairs, self.lifts, state, budget)
        p["lift_details"] = [{"lift_id": l, "lift_name": self.lifts[l].name,
                              "station_name": self.stations[self.lifts[l].station_id]["name"]} for l in p["lifts"]]
        return p

    # -------------------------------------------------------------- evidence
    def explain_pair(self, pair_id: str, scenario_id: str | None = None,
                     candidate_lift: str | None = None) -> dict[str, Any]:
        p = self.pairs_by_id.get(pair_id)
        if not p:
            raise NotFound(pair_id)
        state, sc = self._scenario_state(scenario_id)
        res = I.classify(p, state)
        base = I.classify(p, self.baseline_state)
        restored = None
        if candidate_lift:
            if candidate_lift not in self.lifts:
                raise NotFound(candidate_lift)
            trial = dict(state); trial[candidate_lift] = E.AVAILABLE
            restored = I.classify(p, trial)
        routes = []
        for rt, st in zip(p.routes, res.route_states):
            path = G.route_path(self.db, rt.nodes)
            lifts = []
            for lid in rt.lifts:
                ev = G.lift_evidence(self.db, lid, self.snapshot["id"])
                lifts.append({"id": lid, "name": self.lifts[lid].name, "baseline": self.lifts[lid].baseline.value,
                              "state": state[lid].value, "overridden": lid in sc.get("overrides", {}),
                              "evidence": ev})
            routes.append({"lifts": lifts, "state": st.value, "baseline_state": I.route_state(rt, self.baseline_state).value,
                           "restored_state": I.route_state(rt, trial).value if candidate_lift else None,
                           "path": path})
        return {
            "pair": self._pair_view(p, res, base), "scenario_id": scenario_id, "snapshot": self.freshness(),
            "endpoints": {"a": G.space_evidence(self.db, p.a), "b": G.space_evidence(self.db, p.b)},
            "classification": {"scenario": res.cls.value, "reason": res.reason.value, "baseline": base.cls.value,
                               "with_candidate": restored.cls.value if restored else None,
                               "candidate_lift": candidate_lift},
            "routes": routes,
            "unknowns": self._unknowns(p),
        }

    def _unknowns(self, p: Pair) -> list[str]:
        notes = ["Routes are derived from lift location text; non-lift step-free links (ramps, level access) are not in the source data."]
        if any(x == "UNRESOLVED_PLATFORM" for x in (p.a_role, p.b_role)):
            notes.append("One endpoint is a platform named in text that could not be matched to a NeTEx quay.")
        if "UNKNOWN" in (p.a_assertion.value, p.b_assertion.value):
            notes.append("The source gives no step-free assessment for one endpoint.")
        return notes

    def lift_detail(self, lift_id: str, scenario_id: str | None = None) -> dict[str, Any]:
        if lift_id not in self.lifts:
            raise NotFound(lift_id)
        state, _ = self._scenario_state(scenario_id)
        l = self.lifts[lift_id]
        local = self.pairs_by_station.get(l.station_id, [])
        depending = [p for p in local if any(lift_id in r.lifts for r in p.routes)]
        now = I.evaluate(depending, state)
        out_state = dict(state); out_state[lift_id] = E.UNAVAILABLE
        if_out = I.evaluate(depending, out_state)
        return {"lift": {"id": l.id, "name": l.name, "description": l.description, "baseline": l.baseline.value,
                         "raw_state": l.raw_state, "state": state[lift_id].value,
                         "station_id": l.station_id, "station_name": self.stations[l.station_id]["name"]},
                "evidence": G.lift_evidence(self.db, lift_id, self.snapshot["id"]),
                "pairs_depending": len(depending),
                "confirmed_now": len(now.confirmed()),
                "would_lose_if_unavailable": len(now.confirmed() - if_out.confirmed())}

    def export(self, scenario_id: str) -> dict[str, Any]:
        a = self.analyze(scenario_id)
        r = self.rank(scenario_id, limit=10)
        return {"report": "UNLOCK scenario report", "generated_at": _now(), "analysis": a, "ranking": r,
                "methodology": {
                    "metric": "Confirmed accessible origin–destination pairs (modeled pairs inside a station: platform↔platform, platform↔exit).",
                    "classes": [c.value for c in PairClass],
                    "caveats": ["Counts are modeled pairs, not passengers.",
                                "Scenario overrides are hypothetical; source observations are unchanged.",
                                "Lift→space links are derived from SNCF lift location text (see derivation labels)."]}}
