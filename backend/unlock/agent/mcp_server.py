"""UNLOCK as an MCP server: graph-grounded tools for any agent (Claude Code, Claude Desktop, …).

Run:  python -m unlock mcp [--store database/unlock.rl]

The store is opened READ-ONLY (Relate allows many read-only processes next to the web app),
so an agent can never modify observations, scenarios or the graph. Every number an agent
reports comes from these deterministic tools; simulations are computed in memory only.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from ..config import STORE_PATH
from ..db import GraphStore
from ..engine import impact as I
from ..engine.model import EquipmentStatus
from ..engine.service import UnlockService
from ..network.service import NetworkService
from ..api.explain import explain_pair as narrate

INSTRUCTIONS = """UNLOCK tools answer questions about step-free (lift) accessibility in Île-de-France, using a Relate graph
built from official open data: inside the 401 SNCF stations (lift-by-lift topology) and across the whole regional
rail/metro/tram network (996 stations, GTFS) with the lift outages published in the PRIM traffic feed.
For "can I get from A to B in a wheelchair?" use `check_journey`; for the region-wide picture use `region_overview`.
Rules for the agent:
1. Never state a count, lift id, status or ranking that a tool did not return. Quote tool numbers exactly.
2. Turn free-text outage reports into a lift with `find_lift`. If it returns AMBIGUOUS or NOT_FOUND, ask the
   user (show the candidates) or rephrase the report in French station vocabulary and try again — never guess.
3. Simulations (`simulate_outage`, `rank_repairs` with assumptions) are hypothetical and change nothing; say so.
4. Station counts are modeled platform↔platform / platform↔exit connections inside stations, not people.
   Region counts are ordered station pairs joined by a step-free journey, not trips or people.
5. Give the evidence: lift names, the graph path from `explain_connection`, the status snapshot id and time.
6. The PRIM lift feed and SNCF's hourly lift feed disagree; say which view a number comes from
   ("best" = SNCF hourly status + IDFM lift status for RATP, "feed" = PRIM only, "published" = no outages).
7. For a rider's usual trip ("can I do my trip this morning?") use `usual_trip_alert`; for the lift teams' day,
   `maintenance_bulletin`. Say when the lift status was read (`observed`).
8. When a user says they saw a lift out (or working again), you may store it with `report_lift` — only what they
   saw, never a guess. `field_reports` reads back what riders, staff and other agents reported; a report never
   changes the official status, and you must say whether it confirms or contradicts it."""

_WRITE = re.compile(r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|LOAD|CALL\s+db\.|FOREACH)\b", re.I)


def build_server(store: Path | str = STORE_PATH) -> MCPServer:
    db = GraphStore(store, read_only=True)
    svc = UnlockService(db)
    net = NetworkService(db, svc)
    mcp = MCPServer(name="unlock", title="UNLOCK — Accessibility Impact Graph", instructions=INSTRUCTIONS,
                    version="0.10.0")

    def _ov(lifts: list[str] | None, state: str = "UNAVAILABLE") -> dict[str, str]:
        return {l: state for l in (lifts or [])}

    @mcp.tool()
    def find_lift(report: str) -> dict[str, Any]:
        """Resolve a free-text outage report (French or English) to a lift in the graph.
        Returns status RESOLVED / AMBIGUOUS / NOT_FOUND, ranked candidates with the graph evidence that
        matched, the reported state, and — when resolved — how many confirmed connections depend on it."""
        return svc.resolve_incident(report)

    @mcp.tool()
    def station_overview(station_name: str) -> dict[str, Any]:
        """Lifts of a station with their published status, and its connection counts."""
        r = svc.resolve_incident(station_name + " ascenseur")
        if not r["station_candidates"]:
            return {"status": "NOT_FOUND", "question": "No station matches that name."}
        sid = r["station_candidates"][0]["station_id"]
        g = svc.station_graph(sid)
        return {"station": g["station"]["name"], "lines": [l["short_name"] for l in g["station"]["lines"]],
                "counts": g["counts"], "snapshot": svc.freshness(),
                "lifts": [{"lift_id": l["id"], "name": l["name"], "location": l["description"],
                           "published_status": l["raw_state"], "state": l["state"]} for l in g["lifts"]]}

    @mcp.tool()
    def simulate_outage(lift_ids: list[str], state: str = "UNAVAILABLE") -> dict[str, Any]:
        """Hypothetical: set these lifts to `state` (UNAVAILABLE / AVAILABLE / UNKNOWN) on top of the published
        status and recompute every modeled connection. Returns confirmed connections lost/gained, examples,
        an independent Cypher cross-check, and the repair ranking under that hypothesis. Nothing is saved."""
        return svc.what_if(_ov(lift_ids, state))

    @mcp.tool()
    def rank_repairs(assume_unavailable: list[str] | None = None, limit: int = 10) -> dict[str, Any]:
        """Rank lifts to repair by Δ confirmed step-free connections, over the published status
        (optionally assuming extra lifts are out of service). Includes lifts out of service today."""
        state = I.effective_state(svc.lifts, {k: EquipmentStatus(v) for k, v in _ov(assume_unavailable).items()})
        return svc._rank_state(state, set(assume_unavailable or []), max(1, min(limit, 50)))

    @mcp.tool()
    def plan_repairs(budget: int = 2, assume_unavailable: list[str] | None = None) -> dict[str, Any]:
        """Exact best set of `budget` (1-5) repairs, plus the greedy plan for comparison (lifts in series
        only pay off together)."""
        state = I.effective_state(svc.lifts, {k: EquipmentStatus(v) for k, v in _ov(assume_unavailable).items()})
        p = I.best_plan(svc.pairs, svc.lifts, state, max(1, min(budget, 5)))
        p["lift_details"] = [{"lift_id": l, "lift_name": svc.lifts[l].name,
                              "station": svc.stations[svc.lifts[l].station_id]["name"]} for l in p["lifts"]]
        return p

    @mcp.tool()
    def critical_lifts(limit: int = 10) -> dict[str, Any]:
        """Working lifts whose single failure would cut the most confirmed step-free connections."""
        return svc.critical_lifts(max(1, min(limit, 50)))

    @mcp.tool()
    def explain_connection(pair_id: str, assume_unavailable: list[str] | None = None,
                           candidate_repair: str | None = None) -> dict[str, Any]:
        """Evidence for one connection (pair ids come from simulate_outage examples): the actual Relate path,
        each lift's published status and snapshot, derivation labels, and what remains unknown."""
        d = svc.explain_pair(pair_id, candidate_lift=candidate_repair, overrides=_ov(assume_unavailable) or None)
        return {"classification": d["classification"], "narrative": narrate(d)["statements"],
                "paths": [[(n.get("name") or n.get("id")) for n in (r["path"] or {}).get("nodes", [])] for r in d["routes"]],
                "unknowns": d["unknowns"], "snapshot": d["snapshot"]}

    @mcp.tool()
    def cypher_read(query: str, limit: int = 50) -> dict[str, Any]:
        """Run a READ-ONLY Cypher query on the UNLOCK Relate graph (store opened read-only; max 200 rows).
        Station layer — labels: Station, Quay, Lift, Space, StatusSnapshot, AccessibilityAssertion, TransferZone, Line,
        Dataset; relationships: HAS_LIFT, HAS_QUAY, HAS_SPACE, SERVES (Lift->Space), IS_PLATFORM_OF, HAS_STATUS,
        IN_TRANSFER_ZONE, SERVED_BY (TransferZone->Line), ABOUT, SUPPORTED_BY, REPORTED_IN, DESCRIBED_IN.
        Region layer — labels: NStation, NPlatform (boardable, wheelchair, access_level), NLine, NPattern, OutageFeed,
        LiftOutage; relationships: HAS_PLATFORM, NEXT (stop sequence), LEG (ride between boardable platforms),
        OF_LINE, IS_ZONE (NStation->TransferZone), LISTS, REPORTED_AT, AFFECTS (LiftOutage->NPlatform),
        MATCHES_LIFT (LiftOutage->Lift)."""
        if _WRITE.search(query):
            return {"error": "Only read queries are allowed."}
        rows = db.query(query)
        n = max(1, min(limit, 200))
        return {"rows": json.loads(json.dumps(rows[:n], default=str)), "row_count": len(rows), "truncated": len(rows) > n}

    @mcp.tool()
    def network_summary() -> dict[str, Any]:
        """Graph size, data sources (with sha256), status snapshot freshness and network-wide counts."""
        s = svc.summary()
        return {k: s[k] for k in ("graph", "datasets", "status", "stations", "lifts", "lift_states", "pairs", "coverage")}

    def _station(name: str) -> dict | None:
        hits = net.station_search(name, limit=5)
        return hits[0] if hits else None

    @mcp.tool()
    def check_journey(from_station: str, to_station: str, view: str = "best") -> dict[str, Any]:
        """Is there a step-free (wheelchair) journey between two Île-de-France stations right now?
        Station names are matched against the regional network. Returns the verdict (STEP_FREE,
        STEP_FREE_IF_LIFTS_WORK, CUT_BY_OUTAGES, NO_STEP_FREE_ROUTE_PUBLISHED), the legs (line, board/alight
        platform state), the lift outages on the way, and a Relate re-check of every leg."""
        if not net.ready:
            return {"error": "network layer not imported"}
        a, b = _station(from_station), _station(to_station)
        if not a or not b:
            return {"status": "NOT_FOUND", "question": "Which station? No network station matches "
                    + (from_station if not a else to_station)}
        r = net.check_journey(a["id"], b["id"], view if view in ("best", "feed", "published") else "best")
        r["matched_names"] = {"from": a["name"], "to": b["name"]}
        return r

    @mcp.tool()
    def step_free_reach(from_station: str, view: str = "best") -> dict[str, Any]:
        """Every station a wheelchair user can reach step-free from one station: counts of CONFIRMED,
        IF_LIFTS_WORK, CUT (reachable in the published network but cut by outages), with the daily ticket
        validations of those stations as a weight, and an independent Cypher re-derivation of the confirmed set."""
        if not net.ready:
            return {"error": "network layer not imported"}
        a = _station(from_station)
        if not a:
            return {"status": "NOT_FOUND"}
        r = net.reach(a["id"], view if view in ("best", "feed", "published") else "best")
        cut = sorted((net.stations[s]["name"] for s, c in r["classes"].items() if c == "CUT"))
        doubt_here = [p for p in r["origin_points"] if p["state"] != "OPEN"]
        why = []
        if doubt_here:
            why.append(f"{len(doubt_here)} of {len(r['origin_points'])} boarding points AT THE ORIGIN are not confirmed "
                       f"({', '.join(sorted({p['line'] or '?' for p in doubt_here}))}) because of the outages listed there: "
                       "every journey that needs them is only 'if lifts work'.")
        if r["counts"]["if_lifts_work"]:
            why.append(f"{r['counts']['if_lifts_work']} stations are reachable only through platforms with a listed lift outage.")
        return {k: v for k, v in r.items() if k != "classes"} | {"cut_examples": cut[:15], "why": why}

    @mcp.tool()
    def region_overview() -> dict[str, Any]:
        """Region-wide step-free journeys under three views (published / PRIM feed / best available),
        the outage feed freshness, outage ages and the PRIM-vs-SNCF reconciliation counts."""
        if not net.ready:
            return {"error": "network layer not imported"}
        o = net.overview()
        f, w, s, rec = o["feed"], o["feed_watch"] or {}, o["stale_messages"], o["reconciliation"]
        o["key_facts"] = [
            f"PRIM lists {o['outages']['lifts']} lifts out of service ({o['outages']['messages']} messages); last lift-message "
            f"update {f['last_lift_update']} ({f['lift_messages_stale_days']} days ago); other messages updated {f['last_other_update']}.",
            f"Feed watch: {w.get('observations', 0)} fetches, lift content identical in {w.get('identical_lift_content', 0)}.",
            f"Of the {o['outages']['by_operator'].get('SNCF_GC', 0)} SNCF lifts PRIM lists as broken, SNCF's hourly feed "
            f"contradicts {s['messages_contradicted']} (GHOST {rec.get('GHOST', 0)} matched to one working lift + "
            f"{rec.get('UNRESOLVED_STATION_ALL_WORKING', 0)} at stations where every SNCF lift works); "
            f"{rec.get('CONFIRMED', 0)} confirmed; {rec.get('MISSING_FROM_FEED', 0)} SNCF outages missing from PRIM.",
            f"Confirmed step-free station pairs: published {o['views']['published']['confirmed']}, best "
            f"{o['views']['best']['confirmed']}, PRIM feed {o['views']['feed']['confirmed']}; stale messages hide "
            f"{s['journeys_hidden']}.",
        ]
        if o.get("idfm_status"):
            i = o["idfm_status"]
            o["key_facts"].insert(2, (
                f"IDFM's lift-status dataset (observed {i['observed_at']}) lists {i['ratp_lifts']} RATP lifts: "
                f"{i['ratp_unavailable']} out of service, {i['ratp_unknown']} unknown; on the station lift graphs that closes "
                f"{i['points_closed']} RATP boarding points and leaves {i['points_doubt']} in doubt. It contradicts "
                f"{rec.get('RATP_GHOST', 0)} of the {rec.get('RATP_GHOST', 0) + rec.get('RATP_CONFIRMED', 0) + rec.get('RATP_UNCLEAR', 0)} "
                f"RATP PRIM messages UNLOCK can match to a lift. The best view uses it for RATP lifts."
                + (f" Snapshot taken at night (Paris {i['observed_paris']}): {i['night_closure_suspected']} lifts switched "
                   f"off since 23:00 are counted as unknown (end-of-service shutdown suspected), not as outages."
                   if i.get("night_closure_suspected") else "")))
        return o

    @mcp.tool()
    def region_repairs(limit: int = 10) -> dict[str, Any]:
        """Region-wide: lift repairs that give back the most confirmed step-free journeys (best view), and
        feed corrections (PRIM outages SNCF reports as working) that would stop hiding journeys."""
        return net.rank(max(1, min(limit, 50))) if net.ready else {"error": "network layer not imported"}

    @mcp.tool()
    def station_outages(station_name: str) -> dict[str, Any]:
        """Lift outages the PRIM feed lists at a station (any operator), with age, affected platforms/lines and,
        for SNCF lifts, the matched lift and SNCF's own current status; plus every lift IDFM's lift-status dataset
        lists at the station (RATP and SNCF) with its current status and the lines it serves."""
        s = _station(station_name)
        if not s:
            return {"status": "NOT_FOUND"}
        return {"station": s, "outages": [net.outage_view(o) for o, x in sorted(net.outages.items())
                                          if x["station_id"] == s["id"]],
                "lift_status": net.station_lifts(s["id"]), "lift_status_source": net.idfm_feed}

    @mcp.tool()
    def usual_trip_alert(from_station: str, to_station: str) -> dict[str, Any]:
        """Rider alert: is this usual trip step-free today? Status OK / DETOUR (usual route blocked, step-free
        alternative given) / AT_RISK (only via lifts of uncertain status) / CUT / NO_STEP_FREE_ROUTE, with the lifts
        that block the usual route and the time of the lift-status data used."""
        a, b = _station(from_station), _station(to_station)
        if not a or not b:
            return {"status": "NOT_FOUND", "missing": from_station if not a else to_station}
        return net.trip_status(a["id"], b["id"])

    @mcp.tool()
    def maintenance_bulletin() -> dict[str, Any]:
        """Today's step-free access bulletin for maintenance and passenger-information teams: headline, repairs
        ranked by journeys regained (ties: busiest station first), stations cut off and their lifts, lift-status
        changes since the previous observation, unknown statuses, PRIM messages to correct. Returns Markdown."""
        from ..network import bulletin as B
        b = B.build(net)
        return {"markdown": B.to_markdown(b), "headline": b["headline"], "freshness": b["freshness"]}

    api = os.environ.get("UNLOCK_API_URL", "").rstrip("/")

    def _http(method: str, path: str, body: dict | None = None) -> dict[str, Any]:
        import urllib.error
        import urllib.request
        req = urllib.request.Request(api + path, method=method, headers={"Content-Type": "application/json"},
                                     data=json.dumps(body).encode() if body is not None else None)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            return {"error": f"HTTP {e.code}", "detail": e.read().decode()[:300]}
        except OSError as e:
            return {"error": "UNLOCK server unreachable", "detail": str(e)[:200]}

    @mcp.tool()
    def report_lift(lift_id: str, status: str, note: str = "", reporter: str = "") -> dict[str, Any]:
        """Write a field report into the shared graph: status OUT or WORKING for one lift (get the id from
        `find_lift`, `station_outages` or `field_reports`). Every other agent and the web app read it back. It never
        changes the official status or any journey count; the reply sets it against the official status
        (CONFIRMS / CONTRADICTS / NEW_INFO). Only report what the user says they saw; never invent a report."""
        if not api:
            return {"error": "Reports are written through the UNLOCK server (the one writer of the graph). "
                             "Start `python -m unlock serve` and set UNLOCK_API_URL for this MCP server."}
        return _http("POST", "/api/region/reports", {"lift": lift_id, "status": status, "note": note,
                                                     "source": "agent", "reporter": reporter or "AI agent"})

    @mcp.tool()
    def field_reports(station_name: str = "", hours: float = 24) -> dict[str, Any]:
        """Field reports (riders, staff, AI agents) of the last `hours`, newest first, read from the shared graph,
        each with the lift's official status (the one the best view uses: SNCF's hourly file for SNCF lifts, IDFM's
        dataset for the others) and a verdict CONFIRMS / CONTRADICTS / NEW_INFO, plus what a maintenance team should
        check first. `other_official` gives IDFM's status of the same SNCF lift when it exists: the two official
        sources sometimes disagree. Optional station filter."""
        sid = ""
        if station_name:
            s = _station(station_name)
            if not s:
                return {"status": "NOT_FOUND", "missing": station_name}
            sid = s["id"]
        if api:
            import urllib.parse
            return _http("GET", "/api/region/reports?" + urllib.parse.urlencode({"hours": hours, **({"station": sid} if sid else {})}))
        from ..network import reports as R
        rows = R.reports(net, sid or None, hours)
        return {"reports": rows, "summary": R.summary(rows)}

    mcp._unlock_db = db  # closed by main() before interpreter shutdown
    return mcp


def main(store: str | None = None) -> None:
    server = build_server(store or STORE_PATH)
    try:
        server.run("stdio")
    finally:
        server._unlock_db.close()  # Relate connections must be dropped on their owner thread
