"""Shared fixtures.

``fixture_doc`` is a SYNTHETIC, hand-written station used only for tests.
It is not official data and never ships in the product graph.

Station "Testville" (quays Voie 1, Voie 2, Voie 3):

    Voie 1 --L1-- souterrain --L2-- Voie 2
                  souterrain --L3-- hall (EXIT)
    Voie 1 --L4-- passerelle --L5-- Voie 2      (independent alternative route)
    Voie 3 --L6-- passerelle                     (L6 status UNKNOWN)
    Voie 3 has an UNKNOWN step-free assertion
    L7: "Voie 2" single-sided (unspecified other end)

Expected baseline (all lifts OK except L6 UNKNOWN):
    V1-V2 CONFIRMED (two routes), V1-hall CONFIRMED, V2-hall CONFIRMED,
    V1-V3 UNVERIFIED (L6 unknown + endpoint unknown), V2-V3 UNVERIFIED, V3-hall UNVERIFIED
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from unlock.db import GraphStore  # noqa: E402
from unlock.ingest import spaces  # noqa: E402
from unlock.ingest.load import import_document  # noqa: E402

ST = "FR:99999:LMO:test-station:LOC"
UUID = "test-station"


def _status(snapshot: str, states: dict[str, str]) -> list[dict]:
    m = {"OK": "AVAILABLE", "KO": "UNAVAILABLE", "INCONNU": "UNKNOWN"}
    return [{"id": f"{snapshot}:{lid}", "lift_id": lid, "snapshot_id": snapshot, "state": m[s], "raw_state": s,
             "observed_at": "2026-11-16T10:00:00+00:00", "source_label": lid, "source_location": None}
            for lid, s in sorted(states.items())]


def build_fixture_doc(states: dict[str, str] | None = None, snapshot: str = "fixture@1") -> dict:
    lifts = [("L1", "Voie 1 / souterrain"), ("L2", "Voie 2 / souterrain"), ("L3", "souterrain / Hall"),
             ("L4", "Voie 1 / passerelle"), ("L5", "Voie 2 / passerelle"), ("L6", "Voie 3 / passerelle"),
             ("L7", "Voie 2")]
    codes = {"1": f"{ST}:Q1", "2": f"{ST}:Q2", "3": f"{ST}:Q3"}
    topo = spaces.derive(UUID, set(codes), [(lid, lid, d) for lid, d in lifts])
    states = states or {"L1": "OK", "L2": "OK", "L3": "OK", "L4": "OK", "L5": "OK", "L6": "INCONNU", "L7": "OK"}
    assert_ = {"1": "ACCESSIBLE", "2": "ACCESSIBLE", "3": "UNKNOWN"}
    return {
        "format": "unlock-graph-input/1", "status_snapshot_id": snapshot, "status_observed_at": "2026-11-16T10:00:00+00:00",
        "datasets": [
            {"key": "sncf_netex_accessibility", "title": "FIXTURE netex", "publisher": "fixture", "url": "fixture://netex",
             "licence": "fixture", "licence_url": None, "sha256": "0" * 64, "bytes": 0, "retrieved_at": None,
             "publisher_modified": None, "published": None, "role": "fixture"},
            {"key": "sncf_lift_status", "title": "FIXTURE status", "publisher": "fixture", "url": "fixture://status",
             "licence": "fixture", "licence_url": None, "sha256": "1" * 64, "bytes": 0, "retrieved_at": None,
             "publisher_modified": None, "published": None, "role": "fixture"},
        ],
        "stations": [{"id": ST, "uuid": UUID, "insee": "99999", "name": "Testville", "lon": 2.35, "lat": 48.85,
                      "transport_mode": "rail", "stop_place_type": "railStation", "step_free": "ACCESSIBLE",
                      "wheelchair": "ACCESSIBLE", "mobility_impaired_access": "ACCESSIBLE"}],
        "quays": [{"id": qid, "station_id": ST, "name": f"Voie {c}", "public_code": c, "code": c, "lon": 2.35, "lat": 48.85,
                   "description": None, "step_free": assert_[c], "wheelchair": assert_[c], "lift_free": "ACCESSIBLE",
                   "mobility_impaired_access": assert_[c]} for c, qid in sorted(codes.items())],
        "lifts": [{"id": lid, "station_id": ST, "name": lid, "description": d, "equipment_status_attr": "active",
                   "depth_mm": None, "max_load_kg": None, "width_mm": None, "lon": None, "lat": None} for lid, d in lifts],
        "spaces": [{"id": s.id, "station_id": ST, "name": s.name, "role": s.role,
                    "quay_id": codes.get(s.quay_code) if s.quay_code else None} for _, s in sorted(topo.spaces.items())],
        "serves": [{"lift_id": f.lift_id, "space_id": f.space_id, "derivation": f.derivation,
                    "side_text": f.side_text, "side_index": f.side_index} for f in topo.serves],
        "status_snapshots": _status(snapshot, states),
        "zones": [], "station_zone": [], "lines": [], "zone_lines": [],
    }


@pytest.fixture
def fixture_doc() -> dict:
    return build_fixture_doc()


@pytest.fixture
def store(tmp_path, fixture_doc):
    path = tmp_path / "fixture.rl"
    db = GraphStore(path)
    import_document(db, fixture_doc)
    yield db
    db.close()


def pair_id(a: str, b: str) -> str:
    x, y = sorted([a, b])
    return f"{x}|{y}"


Q1, Q2, Q3 = (f"{UUID}:quay:{c}" for c in "123")
HALL = f"{UUID}:space:hall"
