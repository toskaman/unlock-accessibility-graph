"""HTTP API against a fixture Relate store (real engine, synthetic data)."""
import pytest
from fastapi.testclient import TestClient

from conftest import HALL, Q1, build_fixture_doc, pair_id
from unlock.api.app import create_app
from unlock.db import GraphStore
from unlock.ingest.load import import_document


@pytest.fixture
def client(tmp_path):
    path = tmp_path / "api.rl"
    with GraphStore(path) as db:
        import_document(db, build_fixture_doc())
    with TestClient(create_app(path)) as c:
        yield c


def test_health_and_summary(client):
    assert client.get("/api/health").json()["ok"]
    s = client.get("/api/network/summary").json()
    assert s["pairs"]["TOTAL"] == s["coverage"]["denominator"]
    assert s["graph"]["nodes"]["Lift"] == 7


def test_signature_flow(client):
    st = client.get("/api/network/stations").json()[0]
    g = client.get(f"/api/network/stations/{st['id']}").json()
    assert {l["id"] for l in g["lifts"]} >= {"L1", "L3"}
    r = client.post("/api/scenarios/simulate-outage", json={"lift_ids": ["L3"]})
    assert r.status_code == 201
    sid, a = r.json()["scenario"]["id"], r.json()["analysis"]
    assert a["scenario_counts"]["CONFIRMED_ACCESSIBLE"] == a["baseline_counts"]["CONFIRMED_ACCESSIBLE"] - 2
    rank = client.post(f"/api/scenarios/{sid}/rank-interventions").json()
    assert rank["candidates"][0]["lift_id"] == "L3"
    e = client.get("/api/pairs/explain", params={"pair_id": pair_id(Q1, HALL), "scenario_id": sid, "candidate_lift": "L3"}).json()
    assert e["classification"]["with_candidate"] == "CONFIRMED_ACCESSIBLE"
    assert any(s["kind"] == "OBSERVATION" for s in e["narrative"]["statements"])
    g2 = client.get(f"/api/network/stations/{st['id']}", params={"scenario_id": sid}).json()
    assert next(l for l in g2["lifts"] if l["id"] == "L3")["state"] == "UNAVAILABLE"
    assert next(l for l in g2["lifts"] if l["id"] == "L3")["baseline"] == "AVAILABLE"
    exp = client.post(f"/api/scenarios/{sid}/export").json()
    assert exp["analysis"]["analysis_id"].startswith("ana-")
    assert client.delete(f"/api/scenarios/{sid}").status_code == 204


@pytest.mark.parametrize("bad", ["../etc/passwd", "a b", "x" * 300, "<script>"])
def test_identifier_validation(client, bad):
    assert client.get(f"/api/network/lifts/{bad}").status_code in (404, 422)


def test_unknown_entities_404(client):
    assert client.get("/api/network/lifts/NOPE").status_code == 404
    assert client.get("/api/scenarios/scn-nope").status_code == 404
    assert client.get("/api/pairs/explain", params={"pair_id": "x|y"}).status_code == 404


def test_invalid_overrides_422(client):
    assert client.post("/api/scenarios", json={"overrides": {"L1": "MAYBE"}}).status_code == 422
    assert client.post("/api/scenarios", json={"overrides": {}}).status_code == 422
    assert client.post("/api/scenarios/simulate-outage", json={"lift_ids": []}).status_code == 422


def test_no_arbitrary_cypher_endpoint(client):
    assert client.post("/api/cypher", json={"query": "MATCH (n) DETACH DELETE n"}).status_code in (404, 405)
    assert client.get("/api/debug/queries").json()["queries"]
