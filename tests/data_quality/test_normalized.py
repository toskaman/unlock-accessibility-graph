"""Data-quality checks on the committed normalized snapshot (real data)."""
import json
from pathlib import Path

import pytest

DOC = Path(__file__).resolve().parents[2] / "data" / "normalized" / "graph_input.json"
pytestmark = pytest.mark.skipif(not DOC.exists(), reason="normalized snapshot not built")


@pytest.fixture(scope="module")
def doc():
    return json.loads(DOC.read_text(encoding="utf-8"))


def test_unique_ids(doc):
    for key in ("stations", "quays", "lifts", "spaces", "status_snapshots", "zones", "lines"):
        ids = [r["id"] for r in doc[key]]
        assert len(ids) == len(set(ids)), key


def test_referential_integrity(doc):
    st = {s["id"] for s in doc["stations"]}
    lifts = {l["id"] for l in doc["lifts"]}
    spaces = {s["id"] for s in doc["spaces"]}
    assert all(q["station_id"] in st for q in doc["quays"])
    assert all(l["station_id"] in st for l in doc["lifts"])
    assert all(f["lift_id"] in lifts and f["space_id"] in spaces for f in doc["serves"])
    assert all(o["lift_id"] in lifts for o in doc["status_snapshots"])


def test_status_values_and_unknown_preserved(doc):
    assert {o["state"] for o in doc["status_snapshots"]} <= {"AVAILABLE", "UNAVAILABLE", "UNKNOWN"}
    raw = {(o["raw_state"], o["state"]) for o in doc["status_snapshots"]}
    assert ("INCONNU", "AVAILABLE") not in raw


def test_single_snapshot_per_document(doc):
    assert {o["snapshot_id"] for o in doc["status_snapshots"]} == {doc["status_snapshot_id"]}


def test_coordinates_inside_ile_de_france(doc):
    for s in doc["stations"]:
        assert 1.4 < s["lon"] < 3.6 and 48.1 < s["lat"] < 49.3, s["name"]


def test_every_serves_edge_is_labelled(doc):
    allowed = {"VOIE_TOKEN", "QUAI_NUMBER", "NAME_VOIE_TOKEN", "NAMED_SPACE", "NAMED_SPACE_WITH_TRACK", "UNSPECIFIED_END"}
    assert {f["derivation"] for f in doc["serves"]} <= allowed


# ---- region layer snapshots -------------------------------------------------------
NET = DOC.parent / "network.json"
OUT = DOC.parent / "network_outages.json"


@pytest.mark.skipif(not NET.exists(), reason="network snapshot not built")
def test_network_snapshot_is_consistent():
    from unlock.network.normalize_net import boardable
    net = json.loads(NET.read_text(encoding="utf-8"))
    plats = {p["id"]: p for p in net["platforms"]}
    stations = {s["id"] for s in net["stations"]}
    lines = {l["id"] for l in net["lines"]}
    assert all(p["station_id"] in stations for p in plats.values())
    assert all(pat["line_id"] in lines and len(pat["stops"]) >= 2 and all(s in plats for s in pat["stops"])
               for pat in net["patterns"])
    assert all(p["boardable"] == boardable(p) for p in plats.values())
    assert net["counts"]["boardable_platforms"] == sum(p["boardable"] for p in plats.values())


@pytest.mark.skipif(not OUT.exists(), reason="outage snapshot not built")
def test_outage_snapshot_is_placed_and_free_of_secrets():
    raw = OUT.read_text(encoding="utf-8")
    doc = json.loads(raw)
    net = json.loads(NET.read_text(encoding="utf-8"))
    plats = {p["id"] for p in net["platforms"]}
    assert doc["counts"]["lifts"] == len(doc["outages"]) and len({o["id"] for o in doc["outages"]}) == len(doc["outages"])
    for o in doc["outages"]:
        assert o["affects"], o["id"]
        assert all(a["platform_id"] in plats and a["derivation"] in ("DIRECTION_MATCH", "LINE_AT_STATION", "RAIL_STATION")
                   for a in o["affects"])
        assert o["first_reported"] <= o["last_update"]
    assert "apikey" not in raw.lower() and "token" not in raw.lower()


def test_idfm_lift_snapshot_is_consistent_and_secret_free():
    p = NET.parent / "idfm_lifts.json"
    if not p.exists():
        pytest.skip("no IDFM lift-status snapshot")
    raw = p.read_text(encoding="utf-8")
    doc = json.loads(raw)
    assert doc["counts"]["lifts"] == len(doc["lifts"]) == len({l["id"] for l in doc["lifts"]})
    assert {l["status"] for l in doc["lifts"]} <= {"AVAILABLE", "UNAVAILABLE", "UNKNOWN"}
    assert all(l["status_note"] in (None, "NIGHT_CLOSURE_SUSPECTED") for l in doc["lifts"])
    assert all(l["status"] == "UNKNOWN" for l in doc["lifts"] if l["status_note"])
    assert "apikey" not in raw.lower()
