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
    allowed = {"VOIE_TOKEN", "QUAI_NUMBER", "NAME_VOIE_TOKEN", "NAMED_SPACE", "UNSPECIFIED_END"}
    assert {f["derivation"] for f in doc["serves"]} <= allowed
