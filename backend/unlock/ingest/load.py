"""Import graph_input.json into the Relate store — idempotently.

* Every node is MERGEd on a source-grounded ``id`` protected by a uniqueness
  constraint, so re-importing the same snapshot creates nothing new.
* Status observations are immutable: a ``StatusSnapshot`` is created once per
  (snapshot, lift) and never updated. A new status file adds new snapshots.
* Scenario / analysis nodes are never touched by the importer.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import NORMALIZED_DIR
from ..db import GraphStore

CONSTRAINTS = [
    ("Dataset", "key"), ("Station", "id"), ("Quay", "id"), ("Lift", "id"), ("Space", "id"),
    ("StatusSnapshot", "id"), ("AccessibilityAssertion", "id"), ("TransferZone", "id"),
    ("Line", "id"), ("Scenario", "id"), ("AnalysisResult", "id"), ("ImportRun", "id"),
]
INDEXES = [("StatusSnapshot", "snapshot_id"), ("Space", "role"), ("Station", "name")]

BATCH = 2000


def ensure_schema(db: GraphStore) -> None:
    for label, prop in CONSTRAINTS:
        db.query(f"CREATE CONSTRAINT {label.lower()}_{prop} IF NOT EXISTS FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE")
    for label, prop in INDEXES:
        db.query(f"CREATE INDEX {label.lower()}_{prop}_idx IF NOT EXISTS FOR (n:{label}) ON (n.{prop})")


def _batches(rows: list[dict], n: int = BATCH):
    for i in range(0, len(rows), n):
        yield rows[i:i + n]


STATEMENTS: list[tuple[str, str]] = [
    ("datasets", """UNWIND $rows AS r MERGE (d:Dataset {key: r.key})
        SET d.title = r.title, d.publisher = r.publisher, d.url = r.url, d.licence = r.licence,
            d.licence_url = r.licence_url, d.sha256 = r.sha256, d.bytes = r.bytes,
            d.retrieved_at = r.retrieved_at, d.publisher_modified = r.publisher_modified,
            d.published = r.published, d.role = r.role"""),
    ("stations", """UNWIND $rows AS r MERGE (s:Station {id: r.id})
        SET s.uuid = r.uuid, s.insee = r.insee, s.name = r.name, s.lon = r.lon, s.lat = r.lat,
            s.location = point({longitude: r.lon, latitude: r.lat}),
            s.transport_mode = r.transport_mode, s.stop_place_type = r.stop_place_type
        WITH s MATCH (d:Dataset {key: 'sncf_netex_accessibility'}) MERGE (s)-[:DESCRIBED_IN]->(d)"""),
    ("station_assertions", """UNWIND $rows AS r MATCH (s:Station {id: r.id})
        MATCH (d:Dataset {key: 'sncf_netex_accessibility'})
        MERGE (a:AccessibilityAssertion {id: r.id + '#StepFreeAccess'})
        SET a.dimension = 'StepFreeAccess', a.value = r.step_free, a.scope = 'Station',
            a.source_field = 'StopPlace/AccessibilityAssessment/limitations/AccessibilityLimitation/StepFreeAccess',
            a.wheelchair = r.wheelchair, a.mobility_impaired_access = r.mobility_impaired_access
        MERGE (a)-[:ABOUT]->(s) MERGE (a)-[:SUPPORTED_BY]->(d)"""),
    ("quays", """UNWIND $rows AS r MATCH (s:Station {id: r.station_id})
        MERGE (q:Quay {id: r.id})
        SET q.name = r.name, q.public_code = r.public_code, q.code = r.code, q.lon = r.lon, q.lat = r.lat,
            q.description = r.description
        MERGE (s)-[:HAS_QUAY]->(q)"""),
    ("quay_assertions", """UNWIND $rows AS r MATCH (q:Quay {id: r.id})
        MATCH (d:Dataset {key: 'sncf_netex_accessibility'})
        MERGE (a:AccessibilityAssertion {id: r.id + '#StepFreeAccess'})
        SET a.dimension = 'StepFreeAccess', a.value = r.step_free, a.scope = 'Quay',
            a.source_field = 'Quay/AccessibilityAssessment/limitations/AccessibilityLimitation/StepFreeAccess',
            a.wheelchair = r.wheelchair, a.lift_free = r.lift_free,
            a.mobility_impaired_access = r.mobility_impaired_access
        MERGE (a)-[:ABOUT]->(q) MERGE (a)-[:SUPPORTED_BY]->(d)"""),
    ("lifts", """UNWIND $rows AS r MATCH (s:Station {id: r.station_id})
        MATCH (d:Dataset {key: 'sncf_netex_accessibility'})
        MERGE (l:Lift {id: r.id})
        SET l.name = r.name, l.description = r.description, l.equipment_status_attr = r.equipment_status_attr,
            l.depth_mm = r.depth_mm, l.max_load_kg = r.max_load_kg, l.width_mm = r.width_mm,
            l.lon = r.lon, l.lat = r.lat
        MERGE (s)-[:HAS_LIFT]->(l) MERGE (l)-[:DESCRIBED_IN]->(d)"""),
    ("spaces", """UNWIND $rows AS r MATCH (s:Station {id: r.station_id})
        MERGE (sp:Space {id: r.id}) SET sp.name = r.name, sp.role = r.role
        MERGE (s)-[:HAS_SPACE]->(sp)
        WITH sp, r WHERE r.quay_id IS NOT NULL
        MATCH (q:Quay {id: r.quay_id}) MERGE (sp)-[:IS_PLATFORM_OF]->(q)"""),
    ("serves", """UNWIND $rows AS r MATCH (l:Lift {id: r.lift_id}) MATCH (sp:Space {id: r.space_id})
        MERGE (l)-[e:SERVES {side_index: r.side_index, space_id: r.space_id}]->(sp)
        SET e.derivation = r.derivation, e.side_text = r.side_text"""),
    ("status_snapshots", """UNWIND $rows AS r MATCH (l:Lift {id: r.lift_id})
        MATCH (d:Dataset {key: 'sncf_lift_status'})
        MERGE (o:StatusSnapshot {id: r.id})
        ON CREATE SET o.snapshot_id = r.snapshot_id, o.state = r.state, o.raw_state = r.raw_state,
            o.observed_at = r.observed_at, o.source_label = r.source_label,
            o.source_location = r.source_location, o.dataset_sha256 = d.sha256
        MERGE (l)-[:HAS_STATUS]->(o) MERGE (o)-[:REPORTED_IN]->(d)"""),
    ("zones", """UNWIND $rows AS r MATCH (d:Dataset {key: 'idfm_zones_correspondance'})
        MERGE (z:TransferZone {id: r.id})
        SET z.name = r.name, z.type = r.type, z.town = r.town, z.lon = r.lon, z.lat = r.lat,
            z.in_zdc_reference = r.in_zdc_reference
        MERGE (z)-[:DESCRIBED_IN]->(d)"""),
    ("station_zone", """UNWIND $rows AS r MATCH (s:Station {id: r.station_id}) MATCH (z:TransferZone {id: r.zone_id})
        MERGE (s)-[e:IN_TRANSFER_ZONE]->(z)
        SET e.distance_m = r.distance_m, e.name_score = r.name_score, e.derivation = r.derivation"""),
    ("lines", """UNWIND $rows AS r MATCH (d:Dataset {key: 'idfm_gtfs'})
        MERGE (n:Line {id: r.id})
        SET n.short_name = r.short_name, n.long_name = r.long_name, n.mode = r.mode,
            n.color = r.color, n.text_color = r.text_color
        MERGE (n)-[:DESCRIBED_IN]->(d)"""),
    ("zone_lines", """UNWIND $rows AS r MATCH (z:TransferZone {id: r.zone_id}) MATCH (n:Line {id: r.line_id})
        MERGE (z)-[:SERVED_BY]->(n)"""),
]


def _rows_for(doc: dict, key: str) -> list[dict]:
    if key == "station_assertions":
        return doc["stations"]
    if key == "quay_assertions":
        return doc["quays"]
    return doc.get(key, [])


def import_document(db: GraphStore, doc: dict[str, Any]) -> dict[str, Any]:
    ensure_schema(db)
    before = db.counts()
    for key, cypher in STATEMENTS:
        rows = _rows_for(doc, key)
        for chunk in _batches(rows):
            db.transaction([(cypher, {"rows": chunk})])
    after = db.counts()
    return {"before": before, "after": after}


def run_import(db: GraphStore, path: Path = NORMALIZED_DIR / "graph_input.json") -> dict[str, Any]:
    raw = path.read_bytes()
    doc = json.loads(raw)
    sha = hashlib.sha256(raw).hexdigest()
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = import_document(db, doc)
    run_id = f"import@{sha[:12]}@{started}"
    db.query("""MERGE (r:ImportRun {id: $id}) SET r.input_sha256 = $sha, r.started_at = $at,
                r.status_snapshot_id = $snap, r.format = $fmt""",
             {"id": run_id, "sha": sha, "at": started, "snap": doc["status_snapshot_id"], "fmt": doc["format"]})
    result.update({"run_id": run_id, "input_sha256": sha, "status_snapshot_id": doc["status_snapshot_id"]})
    return result


def import_all(db: GraphStore, normalized_dir: Path = NORMALIZED_DIR) -> dict[str, Any]:
    """Station layer, then (when present) the regional network layer and the PRIM outage feed."""
    result = run_import(db, normalized_dir / "graph_input.json")
    if (normalized_dir / "network.json").exists():
        from ..engine.resolve import build_index
        from ..network.load_net import import_feed_history, import_network, import_outages
        result["network"] = import_network(db, normalized_dir / "network.json")
        result["outages"] = import_outages(db, normalized_dir / "network_outages.json", resolver=build_index(db))
        result["feed_observations"] = import_feed_history(db, normalized_dir / "outage_feed_history.json")
        result["after"] = db.counts()
    return result
