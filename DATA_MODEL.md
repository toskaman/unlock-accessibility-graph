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

Pilot counts (snapshot 2026-11-16): Station 401 · Quay 1,280 · Lift 588 · Space 1,117 · StatusSnapshot 588 ·
AccessibilityAssertion 1,681 · TransferZone 392 · Line 51 · Dataset 4; SERVES 1,369, total 11,761 relationships.

## Region layer (v0.3.0)

| Node | Key properties | Source |
|---|---|---|
| `NStation` | id (= IDFM ZdC id), name, lat/lon, `location` point | GTFS `parent_station` |
| `NPlatform` | id (GTFS stop), station_id, `wheelchair`, `access_level`, `boardable`, modes, lines | GTFS stops + IDFM *Accessibilité en gare* |
| `NLine` | id, short_name, mode (RAIL/METRO/TRAM/CABLE/FUNICULAR), colours, operator | GTFS routes |
| `NPattern` | id, line_id, direction, trips, headsign, terminus_station, length | distinct GTFS stop sequences |
| `NStation.entries_per_day` | average daily validations, Apr–Jun 2026 (724 stations) | `(NStation)-[:ENTRIES_FROM]->(Dataset {key:'idfm_validations_ferre'})` |
| `OutageFeed` | id (`prim_lift_outages@sha`), observed_at, feed_last_lift_update, feed_non_lift_last_update | PRIM snapshot |
| `LiftOutage` | lift_key (`GC:1090`, `RATP:…`), operator, text, first_reported, last_update, announced_until, messages | PRIM `Ascenseur` disruptions grouped per lift |

| Relationship | Meaning | Derivation |
|---|---|---|
| `(NStation)-[:HAS_PLATFORM]->(NPlatform)` | platform of station | GTFS |
| `(NPlatform)-[:NEXT {pattern, seq, line}]->(NPlatform)` | consecutive stops of a pattern | GTFS |
| `(NPlatform)-[:LEG {line, patterns, trips, hops}]->(NPlatform)` | ride between two boardable platforms | `GTFS_PATTERN_BOARDABLE_ENDPOINTS` |
| `(NPattern)-[:OF_LINE]->(NLine)` | pattern of line | GTFS |
| `(NStation)-[:IS_ZONE]->(TransferZone)` | same IDFM ZdC | `SAME_IDFM_ZDC_ID` |
| `(OutageFeed)-[:LISTS]->(LiftOutage)` · `(LiftOutage)-[:REPORTED_AT]->(NStation)` | feed content | PRIM |
| `(LiftOutage)-[:AFFECTS {line_id, derivation, line_derivation}]->(NPlatform)` | platforms the outage concerns | `DIRECTION_MATCH`, `LINE_AT_STATION`, `RAIL_STATION`; lines by `TEXT_NAMES_LINE`, `DIRECTION_NAMES_LINE`, `ALL_LINES_AT_STATION` |
| `(LiftOutage)-[:MATCHES_LIFT {score, evidence}]->(Lift)` | the SNCF lift a G&C message is about | `INCIDENT_RESOLVER_SAME_ZONE`, only RESOLVED |

Counts (snapshot 2026-11-16): NStation 996 · NPlatform 1,953 · NLine 59 · NPattern 1,055 · NEXT 14,077 · LEG 14,147 ·
IS_ZONE 392 · LiftOutage 356 · AFFECTS 583 · MATCHES_LIFT 168.

## Lift status, alerts, regions (v0.6.0)

```
(:LiftStatusFeed {id: "idfm_etat_ascenseurs@<sha12>", observed_at, sha256, lifts, night_closure_suspected})
   -[:LISTS]->(:IdfmLift {id, operator RATP|SNCF, status AVAILABLE|UNAVAILABLE|UNKNOWN, status_note, raw_status,
                          reason, updated, direction, situation, sides_json})
(:IdfmLift)-[:AT]->(:NStation)                                   same IDFM ZdC id
(:IdfmLift)-[:CONNECTS {line_id, side, derivation}]->(:NPlatform)  a platform side of the lift (DIRECTION_MATCH | LINE_AT_STATION)
(:IdfmLift)-[:SAME_LIFT {derivation: SAME_ID}]->(:Lift)           SNCF lifts: same id as the NeTEx station layer
(:LiftOutage)-[:REPORTS_ON {derivation: SIRI_EQUIPMENT_ID}]->(:IdfmLift)   PRIM message ↔ lift
(:LiftStatusFeed)-[:OBSERVED_AS]->(:LiftStatusObservation {observed_at, lifts, not_available, not_available_json})
(:Region {code, name, network_label, center, zoom})              only in second-region stores
(:NStation)-[:ENTRIES_FROM]->(:Dataset)                          IDFM validations, or SNCF Fréquentation en gares
```

The service reads only the latest `LiftStatusFeed`. Rider trips are not stored anywhere on the server.
A second region is a separate store (`database/regions/<code>.rl`) with the same labels; its `NStation.id` is the
GTFS stop-area id (`OCE87723197`) and `TransferZone` nodes are those stop areas (`zones_dataset: sncf_gtfs`).

## v0.7.0

History lives in files, not in the store (`data/normalized/history/`): it spans store rebuilds. Each region store is
built the same way (`(:Region)` node, `NStation.id` = national stop area id). The zero-install demo's
`graph.json` is a compact projection of `NStation`, `NPlatform`, `HAS_PLATFORM`, `LEG` and `NEXT` that the browser
re-imports into an in-memory Relate (WebAssembly) database with the same labels.
