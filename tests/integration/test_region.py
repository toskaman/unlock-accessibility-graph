"""Region layer end to end on a real Relate store: import, resolver matching, three views, ranking, API."""
import json

import pytest
from fastapi.testclient import TestClient

from conftest import build_fixture_doc
from region_fixture import idfm_lifts, line_reports, network
from unlock.api.app import create_app
from unlock.db import GraphStore
from unlock.engine.resolve import build_index
from unlock.engine.service import UnlockService
from unlock.ingest.load import import_document
from unlock.network.idfm_lifts import normalize_file
from unlock.network.load_net import import_idfm_lifts, import_network, import_outages
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


def test_idfm_lift_status_replaces_prim_for_ratp(region_store, tmp_path):
    raw = tmp_path / "idfm_raw.json"
    raw.write_text(json.dumps(idfm_lifts()), encoding="utf-8")
    normalize_file(network(), raw=raw, out=tmp_path / "idfm_lifts.json")
    with GraphStore(region_store) as db:
        res = import_idfm_lifts(db, tmp_path / "idfm_lifts.json")
    assert res["lifts"] == 3 and res["connects"] == 1 and res["same_lift"] == 1
    with GraphStore(region_store, read_only=True) as db:
        ns = NetworkService(db, UnlockService(db))
        assert ns.ratp_states["M:Z3a|M1"] == ("CLOSED", "STATION_LIFT_GRAPH")
        assert "M:Z3b|M1" not in ns.ratp_states            # arrival-only quay: no lift lists it
        o = ns.overview()
        assert o["idfm_status"]["ratp_lifts"] == 2 and o["idfm_status"]["points_closed"] == 1
        # the closed quay is not even "possible" any more in the best view
        assert o["views"]["best"]["confirmed"] == 9 and o["views"]["best"]["possible"] == 9
        rank = ns.rank(5)
        top = rank["repairs"][0]
        assert top["kind"] == "RATP_LIFT" and top["lift"].endswith("501:LOC") and top["gain"] > 0
        lifts = ns.station_lifts("Z3")
        assert [l["status"] for l in lifts] == ["UNAVAILABLE", "AVAILABLE"] and lifts[0]["lines"] == ["1"] and lifts[1]["lines"] == []


def test_rider_alerts_and_bulletin(region_store, tmp_path):
    raw = tmp_path / "idfm_raw.json"
    raw.write_text(json.dumps(idfm_lifts()), encoding="utf-8")
    normalize_file(network(), raw=raw, out=tmp_path / "idfm_lifts.json")
    assert (tmp_path / "idfm_lift_history.json").exists()
    with GraphStore(region_store) as db:
        assert import_idfm_lifts(db, tmp_path / "idfm_lifts.json")["observations"] == 1
    from unlock.network import bulletin
    from unlock.network.alerts import run_file
    with GraphStore(region_store, read_only=True) as db:
        ns = NetworkService(db, UnlockService(db))
        assert ns.trip_status("Z2", "Z1")["status"] == "OK"
        t = ns.trip_status("Z1", "Z4")          # R1 to Beta, then M1 from the quay whose only lift is out
        assert t["status"] == "CUT" and t["usual_blocked_at"][0]["state"] == "CLOSED"
        assert "cut at Beta" in t["message"] and t["blocking"][0]["lift"].endswith("501:LOC")
        trips = tmp_path / "trips.json"
        trips.write_text(json.dumps({"trips": [{"label": "work", "from": "Testville", "to": "Gamma", "last_status": "OK"}]}))
        res = run_file(ns, trips, tmp_path / "reports")
        assert res["trips"][0]["status"] == "CUT" and res["trips"][0]["changed"] is True
        saved = json.loads(trips.read_text())["trips"][0]
        assert saved["last_status"] == "CUT" and saved["usual"][0]["line"] == "R1"
        b = bulletin.build(ns)
        assert b["repairs"][0]["kind"] == "RATP_LIFT" and b["changes"]["since"] is None
        md, page = bulletin.to_markdown(b), bulletin.to_html(b)
        assert "## Fix first" in md and "Beta" in md and page.startswith("<!DOCTYPE html>") and "<script" not in page
    app = create_app(region_store)
    with TestClient(app) as c:
        r = c.post("/api/region/trips/check", json={"trips": [{"from": "Z1", "to": "Z4"}, {"from": "nowhere", "to": "Z4"}]})
        assert r.status_code == 200 and [x["status"] for x in r.json()["trips"]] == ["CUT", "UNKNOWN_STATION"]
        assert c.post("/api/region/trips/check", json={"trips": []}).status_code == 422
        assert c.post("/api/region/trips/check", json={"trips": [{"from": "Z1", "to": "Z4",
                      "usual": [{"board": "R:Z1", "alight": "R:Z3", "line": "nope"}]}]}).status_code == 422
        assert c.get("/api/region/bulletin").json()["format"] == "unlock-bulletin/1"
        assert c.get("/api/region/bulletin.html").text.startswith("<!DOCTYPE html>")


def test_several_regions_served_side_by_side(region_store, tmp_path):
    import shutil
    other = tmp_path / "other.rl"
    shutil.copytree(region_store, other) if region_store.is_dir() else shutil.copy(region_store, other)
    with TestClient(create_app(region_store, regions={"zz": other})) as c:
        rs = c.get("/api/regions").json()
        assert [r["code"] for r in rs] == ["idf", "zz"] and rs[0]["default"] and not rs[1]["default"]
        a = c.get("/api/region/overview").json()
        b = c.get("/api/region/overview?region=zz").json()
        assert b["region"]["code"] == "zz" and a["views"]["published"] == b["views"]["published"]
        assert c.get("/api/region/overview?region=nope").status_code == 404
        assert c.post("/api/region/trips/check?region=zz", json={"trips": [{"from": "Z2", "to": "Z1"}]}).json()["trips"][0]["status"] == "OK"


def test_lift_out_at_station_without_street_topology_is_doubt(region_store):
    from unlock.engine.model import EquipmentStatus as LiftState
    with GraphStore(region_store, read_only=True) as db:
        ns = NetworkService(db, UnlockService(db))
        assert ns._p_all.get("Z1")                       # Testville is modelled
        ns._p_all["Z1"] = set()                          # pretend the lift text gave no platform↔exit route
        any_lift = ns._lifts_at[ns.sncf_of["Z1"][0]][0]
        ns.ss.baseline_state[any_lift] = LiftState.UNAVAILABLE
        states = ns.view_states("best")
        assert all(states.get(p) == "DOUBT" for p in ns.rail_platforms["Z1"])


def test_trip_subscription_feeds(region_store):
    import xml.etree.ElementTree as ET
    with TestClient(create_app(region_store, regions={})) as c:
        r = c.get("/api/region/trips/feed.rss", params={"from": "Testville", "to": "Gamma"})
        assert r.status_code == 200 and r.headers["content-type"].startswith("application/rss+xml")
        item = ET.fromstring(r.text).find("channel/item")
        assert item.find("title").text.startswith("Testville → Gamma: ")
        i = c.get("/api/region/trips/feed.ics", params={"from": "Z1", "to": "Z4"})
        assert i.status_code == 200 and i.text.startswith("BEGIN:VCALENDAR\r\n") and "BEGIN:VEVENT" in i.text
        assert all(len(l.encode()) <= 75 for l in i.text.split("\r\n"))
        assert c.get("/api/region/trips/feed.xml", params={"from": "Z1", "to": "Z4"}).status_code == 404
        assert c.get("/api/region/trips/feed.rss", params={"from": "nowhere", "to": "Z4"}).status_code == 404


def test_region_metrics_history_and_compare(region_store, tmp_path, monkeypatch):
    from unlock import history as H
    monkeypatch.setattr(H, "HIST", tmp_path / "hist")
    with GraphStore(region_store, read_only=True) as db:
        ns = NetworkService(db, UnlockService(db))
        row = H.region_metrics(ns, "idf")
        assert row["published"] == 12 and row["confirmed"] == 9 and "Z3" in row["station_states"]
        H.append_metrics([row])
        H.append_metrics([row])                            # same observation twice → kept once
        assert len(H.region_series("idf")["observations"]) == 1
    with TestClient(create_app(region_store, regions={})) as c:
        assert c.get("/api/region/history").json()["region"] == "idf"
        rows = c.get("/api/regions/compare").json()["regions"]
        assert rows[0]["code"] == "idf" and rows[0]["published"] == 12 and rows[0]["confirmed"] == 9
