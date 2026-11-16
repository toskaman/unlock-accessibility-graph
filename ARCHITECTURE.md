# Architecture

```
 official sources                 ETL (deterministic)                    Relate (single file)              API + UI
 ───────────────                  ──────────────────                     ────────────────────              ────────
 SNCF NeTEx accessibility ─┐
 SNCF lift status (hourly) ┼─ fetch_sources.py ─ normalize.py ─────► graph_input.json ─ load.py ─► database/unlock.rl
 IDFM transfer zones       │  (sha256 manifest)  (parse, derive,          (committed,           (MERGE on      │
 IDFM GTFS (lines)        ─┘
 IDFM GTFS + Accessibilité en gare ─ network/gtfs_net.py ──────► network.json ───────── network/load_net.py ─► (same store)
 PRIM Messages Info Trafic (token) ─ network/prim.py ─ outages.py ► network_outages.json ─┘  + resolver → MATCHES_LIFT                      label every edge)       ODbL)                 constrained ids)│
                                                                                                                │
                              GraphStore (one owner thread, parameterised Cypher, serialised writes) ◄──────────┘
                                         │
                       engine/graph.py ── Cypher: routes (ACYCLIC QPP), assertions, states, evidence, paths
                       engine/impact.py ─ pure functions: route state, pair class, diff, rank, exact plan
                       engine/service.py ─ scenarios + analyses persisted back into Relate
                       network/engine.py ─ exact station-pair reachability (SCC + bitsets), least-cost journeys
                       network/service.py ─ three views, ranking, reconciliation, Cypher re-check of journey legs
                                         │
                       api/app.py (FastAPI, 127.0.0.1, typed, no arbitrary Cypher) ── api/explain.py (Analyst)
                                         │
                       frontend (React + TypeScript + MapLibre): map · station cross-section · ranking · evidence
```

## Why Relate, and how it is used

* **Embedded, single file.** `database/unlock.rl` is the system of record: 6.5 MB, 6,102 domain nodes and 11,761
  relationships for the pilot (plus one `ImportRun` record per import). No server, no sign-up — judges open the same file the app uses.
* **The core question is a traversal.** "Which lifts does a step-free connection between Voie 40 and
  Voie 50 depend on, and is there an alternative?" is an acyclic variable-length path query over
  `Space–Lift–Space` chains (`ACYCLIC (a)-[:SERVES]-{2,10}(b)`). Series vs parallel lifts fall out of
  the path set; a spreadsheet of lifts cannot express it.
* **Provenance is graph structure.** Every status observation, assertion and lift is linked to the
  `:Dataset` node holding the file sha256, so the evidence panel is a graph query, not a lookup table.
* **Scenarios live in the graph.** `(:Scenario)-[:OVERRIDES]->(:Lift)` and
  `(:Scenario)-[:PRODUCES]->(:AnalysisResult)`; observations are immutable.

Bounded application-side work: after one traversal the engine keeps the *route structure*
(pair → minimal lift sets) in memory and evaluates scenario states over it in milliseconds. Relate stays
authoritative — the cache is rebuilt from Relate at startup and on `reload()`, and every explanation
re-reads the path and evidence from the store.

## Concurrency and lifecycle (respecting Relate's limits)

* `relate.threadsafety == 1` and a file store admits **one writable open**. `GraphStore` opens the
  connection on a dedicated single-thread executor; every query from any FastAPI thread is submitted to it.
  Writes are therefore serialised; multi-statement writes use explicit transactions (rollback on error).
* Uvicorn runs with `workers=1`. A second writer is refused by Relate (tested).
* On startup failure the store is closed before re-raising, releasing the lease.

## Security posture (local prototype)

Binds to `127.0.0.1`; CORS limited to the Vite dev origin; identifiers validated against
`^[A-Za-z0-9:._|-]{1,200}$`; all Cypher parameterised (injection test); no endpoint accepts Cypher;
the runtime model (optional) only rephrases computed facts and is rejected if it introduces any number;
downloads are size-capped; raw data is written only under `data/raw`.
