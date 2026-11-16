"""Agent-facing features: graph-grounded incident resolution, transient what-if, criticality, MCP server."""
import asyncio
import json
import sys
from pathlib import Path

import pytest

from conftest import HALL, Q1, Q2, build_fixture_doc, pair_id
from unlock.db import GraphStore
from unlock.engine.service import UnlockService
from unlock.ingest.load import import_document


def test_resolve_incident_grounded_in_serves_edges(store):
    svc = UnlockService(store)
    r = svc.resolve_incident("Testville : ascenseur voie 3 en panne depuis ce matin")
    assert r["status"] == "RESOLVED" and r["lift_candidates"][0]["lift_id"] == "L6"
    assert any("SERVES" in e for e in r["lift_candidates"][0]["evidence"])
    assert r["reported_state"] == "UNAVAILABLE"


def test_resolve_incident_abstains_instead_of_guessing(store):
    svc = UnlockService(store)
    amb = svc.resolve_incident("Testville ascenseur en panne")
    assert amb["status"] == "AMBIGUOUS" and amb["question"] and len(amb["lift_candidates"]) > 1
    assert svc.resolve_incident("Panne à la gare de Nulle-Part")["status"] == "NOT_FOUND"
    assert svc.resolve_incident("Testville voie 1 ascenseur remis en service")["reported_state"] == "AVAILABLE"


def test_what_if_is_not_persisted(store):
    svc = UnlockService(store)
    w = svc.what_if({"L3": "UNAVAILABLE"})
    assert w["confirmed_lost"] == 2 and w["relate_crosscheck"]["all_match"]
    assert {e["pair_id"] for e in w["lost_examples"]} == {pair_id(Q1, HALL), pair_id(Q2, HALL)}
    assert store.query("MATCH (n) WHERE n:Scenario OR n:AnalysisResult RETURN count(n) AS n")[0]["n"] == 0


def test_critical_lifts_single_points_of_failure(store):
    c = UnlockService(store).critical_lifts()
    top = c["lifts"][0]
    assert top["lift_id"] == "L3" and top["would_lose"] == 2
    l1 = next(x for x in c["lifts"] if x["lift_id"] == "L1")
    assert l1["would_lose"] == 0 and l1["covered_by_alternative"] > 0   # redundancy via the footbridge


def test_mcp_server_read_only_tools(tmp_path):
    pytest.importorskip("mcp")
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    path = tmp_path / "mcp.rl"
    with GraphStore(path) as db:
        import_document(db, build_fixture_doc())
    backend = str(Path(__file__).resolve().parents[2] / "backend")

    async def run():
        params = StdioServerParameters(command=sys.executable, args=["-m", "unlock", "mcp", "--store", str(path)],
                                       env={"PYTHONPATH": backend})
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                names = {t.name for t in (await s.list_tools()).tools}
                found = json.loads((await s.call_tool("find_lift", {"report": "Testville voie 3 HS"})).content[0].text)
                sim = json.loads((await s.call_tool("simulate_outage", {"lift_ids": ["L3"]})).content[0].text)
                bad = json.loads((await s.call_tool("cypher_read", {"query": "MATCH (n) DETACH DELETE n"})).content[0].text)
                ok = json.loads((await s.call_tool("cypher_read", {"query": "MATCH (l:Lift) RETURN count(l) AS n"})).content[0].text)
                return names, found, sim, bad, ok
    names, found, sim, bad, ok = asyncio.run(run())
    assert {"find_lift", "simulate_outage", "rank_repairs", "explain_connection", "cypher_read"} <= names
    assert found["lift_candidates"][0]["lift_id"] == "L6"
    assert sim["confirmed_lost"] == 2
    assert "error" in bad and ok["rows"][0]["n"] == 7
    with GraphStore(path, read_only=True) as db:   # nothing was written by the agent session
        assert db.query("MATCH (l:Lift) RETURN count(l) AS n")[0]["n"] == 7
