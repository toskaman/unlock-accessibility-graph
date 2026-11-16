"""UNLOCK as an MCP server: graph-grounded tools for any agent (Claude Code, Claude Desktop, …).

Run:  python -m unlock mcp [--store database/unlock.rl]

The store is opened READ-ONLY (Relate allows many read-only processes next to the web app),
so an agent can never modify observations, scenarios or the graph. Every number an agent
reports comes from these deterministic tools; simulations are computed in memory only.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from ..config import STORE_PATH
from ..db import GraphStore
from ..engine import impact as I
from ..engine.model import EquipmentStatus
from ..engine.service import UnlockService
from ..api.explain import explain_pair as narrate

INSTRUCTIONS = """UNLOCK tools answer questions about step-free (lift) accessibility in the 401 SNCF stations of
Île-de-France, using a Relate graph built from official open data (SNCF Gares & Connexions, IDFM).
Rules for the agent:
1. Never state a count, lift id, status or ranking that a tool did not return. Quote tool numbers exactly.
2. Turn free-text outage reports into a lift with `find_lift`. If it returns AMBIGUOUS or NOT_FOUND, ask the
   user (show the candidates) or rephrase the report in French station vocabulary and try again — never guess.
3. Simulations (`simulate_outage`, `rank_repairs` with assumptions) are hypothetical and change nothing; say so.
4. Counts are modeled platform↔platform / platform↔exit connections inside stations, not people.
5. Give the evidence: lift names, the graph path from `explain_connection`, the status snapshot id and time."""

_WRITE = re.compile(r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|LOAD|CALL\s+db\.|FOREACH)\b", re.I)


def build_server(store: Path | str = STORE_PATH) -> MCPServer:
    db = GraphStore(store, read_only=True)
    svc = UnlockService(db)
    mcp = MCPServer(name="unlock", title="UNLOCK — Accessibility Impact Graph", instructions=INSTRUCTIONS,
                    version="0.2.0")

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
        Labels: Station, Quay, Lift, Space, StatusSnapshot, AccessibilityAssertion, TransferZone, Line, Dataset.
        Relationships: HAS_LIFT, HAS_QUAY, HAS_SPACE, SERVES (Lift->Space), IS_PLATFORM_OF, HAS_STATUS,
        IN_TRANSFER_ZONE, SERVED_BY (TransferZone->Line), ABOUT, SUPPORTED_BY, REPORTED_IN, DESCRIBED_IN."""
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

    mcp._unlock_db = db  # closed by main() before interpreter shutdown
    return mcp


def main(store: str | None = None) -> None:
    server = build_server(store or STORE_PATH)
    try:
        server.run("stdio")
    finally:
        server._unlock_db.close()  # Relate connections must be dropped on their owner thread
