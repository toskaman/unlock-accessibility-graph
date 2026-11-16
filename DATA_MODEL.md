# Graph data model (Relate)

All ids are source identifiers; uniqueness constraints exist on every `id`/`key` below.

| Label | Key | From | Notes |
|---|---|---|---|
| `Dataset` | `key` | manifest | url, licence, sha256, bytes, retrieved_at, publisher_modified, published |
| `Station` | `id` = NeTEx StopPlace id | NeTEx | name, lon/lat, `location` (point), INSEE |
| `Quay` | NeTEx Quay id | NeTEx | name ("Voie 2"), code, public_code |
| `AccessibilityAssertion` | `<subject>#StepFreeAccess` | NeTEx | value ACCESSIBLE/INACCESSIBLE/UNKNOWN, source_field path |
| `Lift` | SNCF equipment UUID | NeTEx | name, description (location text), depth, max load |
| `StatusSnapshot` | `<snapshot_id>:<lift>` | SNCF status | state, raw_state (OK/KO/INCONNU), observed_at — **immutable** |
| `Space` | `<station uuid>:quay:<code>` or `:space:<slug>` or `:unspecified:<lift>` | derived | role PLATFORM, UNRESOLVED_PLATFORM, CONNECTOR, EXIT, PRIVATE, UNRESOLVED, UNSPECIFIED |
| `TransferZone` | IDFM ZdC id | IDFM ZdC + GTFS | name, type, town |
| `Line` | GTFS route_id | IDFM GTFS | short name, mode, colours (bus excluded) |
| `Scenario` | `scn-…` | app | kind, base_snapshot_id, algorithm_version, `simulated = true` |
| `AnalysisResult` | `ana-<input hash>` | app | counts, lost/gained, summary_json |
| `ImportRun` | `import@<sha>@<time>` | app | input sha256, snapshot id |

| Relationship | Meaning | Grounding |
|---|---|---|
| `(Station)-[:HAS_QUAY]->(Quay)` | quay belongs to station | source structure |
| `(Station)-[:HAS_LIFT]->(Lift)` | lift belongs to station | source structure |
| `(Station)-[:HAS_SPACE]->(Space)` | space inside station | derived |
| `(Lift)-[:SERVES {derivation, side_text, side_index}]->(Space)` | lift has an end in this space | **derived from lift location text**, label in `derivation` |
| `(Space)-[:IS_PLATFORM_OF]->(Quay)` | platform space = this quay | exact token match |
| `(AccessibilityAssertion)-[:ABOUT]->(Quay|Station)` | step-free assessment | source |
| `(AccessibilityAssertion)-[:SUPPORTED_BY]->(Dataset)` | provenance | source |
| `(Lift)-[:HAS_STATUS]->(StatusSnapshot)-[:REPORTED_IN]->(Dataset)` | observation + provenance | source |
| `(Station|Lift|TransferZone|Line)-[:DESCRIBED_IN]->(Dataset)` | provenance | source |
| `(Station)-[:IN_TRANSFER_ZONE {distance_m, name_score, derivation}]->(TransferZone)` | anchoring in IDFM reference | derived (name + distance) |
| `(TransferZone)-[:SERVED_BY]->(Line)` | a line calls at the zone | GTFS stop_times/trips |
| `(Scenario)-[:OVERRIDES {state}]->(Lift)` | hypothetical lift state | user action |
| `(Scenario)-[:BASED_ON {snapshot_id}]->(Dataset)` | baseline used | app |
| `(Scenario)-[:PRODUCES]->(AnalysisResult)` | reproducible result | app |

`SERVES.derivation` values: `VOIE_TOKEN`, `QUAI_NUMBER`, `NAME_VOIE_TOKEN`, `NAMED_SPACE`,
`UNSPECIFIED_END` — defined in `backend/unlock/ingest/spaces.py`. An `UNSPECIFIED` space is a per-lift
placeholder and can never join two anchors.

Pilot counts (snapshot 2026-11-16): Station 401 · Quay 1,280 · Lift 588 · Space 1,092 · StatusSnapshot 588 ·
AccessibilityAssertion 1,681 · TransferZone 392 · Line 51 · Dataset 4; SERVES 1,318, total 11,680 relationships.
