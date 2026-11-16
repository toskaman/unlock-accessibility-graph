"""Region layer end to end on a real Relate store: import, resolver matching, three views, ranking, API."""
import json

import pytest
from fastapi.testclient import TestClient

from conftest import build_fixture_doc
from region_fixture import line_reports, network
from unlock.api.app import create_app
from unlock.db import GraphStore
from unlock.engine.resolve import build_index
from unlock.engine.service import UnlockService
from unlock.ingest.load import import_document
from unlock.network.load_net import import_network, import_outages
from unlock.network.normalize_net import build_outages_file
from unlock.network.service import NetworkService


def _doc():
    d = build_fixture_doc()
    d["datasets"].append({"key": "idfm_zones_correspondance", "title": "FIXTURE zones", "publisher": "fixture",
                          "url": "fixture://zones", "licence": "fixture", "licence_url": None, "sha256": "2" * 64,
                          "bytes": 0, "retrieved_at": None, "publisher_modified": None, "published": None, "role": "fixture"})
    d["zones"] = [{"id": "Z1", "name": "Testville", "type": "railStation", "town": "Testville", "lon": 2.35, "lat": 48.85,
                   "in_zdc_reference": True}]
    d["station_zone"] = [{"station_id": d["stations"][0]["id"], "zone_id": "Z1", "distance_m": 0.0, "name_score": 1.0,
                          "derivation": "NAME_AND_DISTANCE"}]
    return d


@pytest.fixture
def region_store(tmp_path):
    net = network()
    (tmp_path / "network.json").write_text(json.dumps(net))
    raw = tmp_path / "line_reports.json"
    raw.write_text(json.dumps(line_reports()))
    build_outages_file(net, raw_file=raw, out_dir=tmp_path)
    path = tmp_path / "region.rl"
    with GraphStore(path) as db:
        import_document(db, _doc())
        import_network(db, tmp_path / "network.json")
        res = import_outages(db, tmp_path / "network_outages.json", resolver=build_index(db))
        assert res["outages"] == 2 and res["matched"] == {"RESOLVED": 1}
        assert db.query("MATCH (:LiftOutage)-[:MATCHES_LIFT]->(l:Lift) RETURN l.id AS id")[0]["id"] == "L3"
    return path


def test_three_views_and_reconciliation(region_store):
    with GraphStore(region_store, read_only=True) as db:
        ns = NetworkService(db, UnlockService(db))
        o = ns.overview()
        assert o["views"]["published"]["confirmed"] == 12
        # feed: with L3 down no Testville platform reaches the street on the station topology (CLOSED);
        # the Beta quay towards Gamma is in doubt
        assert o["views"]["feed"]["confirmed"] == 4 and o["views"]["feed"]["possible"] == 6
        # best: SNCF says L3 works -> only the RATP quay remains in doubt
        assert o["views"]["best"]["confirmed"] == 9
        assert o["reconciliation"]["GHOST"] == 1
        assert o["feed"]["lift_messages_stale_days"] >= 0
        assert o["stale_messages"]["journeys_hidden"] == 5
        r = ns.rank(5)
        assert r["repairs"][0]["kind"] == "RATP_FEED_OUTAGE" and r["repairs"][0]["gain"] == 3
        assert r["corrections"][0]["verdict"] == "GHOST" and r["corrections"][0]["gain"] == 5
        j = ns.check_journey("Z1", "Z4", "best")
        assert j["verdict"] == "STEP_FREE_IF_LIFTS_WORK" and j["verification"]["ok"]
        assert j["blocking_outages"][0]["operator"] == "RATP"
        assert ns.check_journey("Z4", "Z2", "best")["verdict"] == "STEP_FREE"
        assert ns.check_journey("Z1", "Z5", "published")["verdict"] == "NO_STEP_FREE_ROUTE_PUBLISHED"


def test_reach_classes_and_cypher_rederivation(region_store):
    with GraphStore(region_store, read_only=True) as db:
        ns = NetworkService(db, UnlockService(db))
        r = ns.reach("Z1", "best")      # Testville: Alpha and Beta confirmed; Gamma needs the Beta quay in doubt
        assert r["classes"]["Z2"] == "CONFIRMED" and r["classes"]["Z3"] == "CONFIRMED"
        assert r["classes"]["Z4"] == "IF_LIFTS_WORK" and r["classes"]["Z5"] == "NOT_BOARDABLE"
        assert r["verification"]["ok"] and r["verification"]["cypher"] == 2
        f = ns.reach("Z2", "feed")      # feed: Testville CLOSED, Gamma only if lifts work
        assert f["classes"]["Z1"] == "CUT" and f["counts"] == {"confirmed": 1, "if_lifts_work": 1, "cut": 1, "published": 3}
        assert f["verification"]["ok"]


def test_region_api(region_store):
    with TestClient(create_app(region_store)) as c:
        assert c.get("/api/region/overview").json()["views"]["best"]["confirmed"] == 9
        m = c.get("/api/region/map", params={"view": "feed"}).json()
        st = {s["id"]: s["state"] for s in m["stations"]}
        assert st["Z1"] == "CLOSED" and st["Z5"] == "NOT_BOARDABLE"
        assert c.get("/api/region/map", params={"view": "nope"}).status_code == 422
        j = c.get("/api/region/journey", params={"from": "Z2", "to": "Z4"}).json()
        assert j["legs"] and j["legs"][0]["path"]
        assert c.get("/api/region/journey", params={"from": "Z2", "to": "nope"}).status_code == 404
        assert c.get("/api/region/stations", params={"q": "gam"}).json()[0]["id"] == "Z4"
        assert c.get("/api/region/reach", params={"from": "Z4"}).json()["counts"]["confirmed"] == 3
        assert c.get("/api/region/reach", params={"from": "nope"}).status_code == 404
        rec = c.get("/api/region/reconciliation").json()
        assert rec["rows"][0]["lift_name"] == "L3"
        oid = rec["rows"][0]["outage"]
        assert c.get(f"/api/region/outages/{oid}").json()["matched_lifts"][0]["sncf_state"] == "AVAILABLE"


def test_region_absent_is_graceful(tmp_path):
    path = tmp_path / "plain.rl"
    with GraphStore(path) as db:
        import_document(db, build_fixture_doc())
    with TestClient(create_app(path)) as c:
        assert c.get("/api/region/overview").status_code == 404
        assert c.get("/api/health").json()["ok"]
