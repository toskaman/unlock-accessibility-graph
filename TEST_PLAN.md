# Test plan

| Layer | Command | Count | What it proves |
|---|---|---|---|
| Unit — parser | `pytest tests/unit/test_spaces.py` | 10 | Real description strings → correct spaces/derivations; unknown tracks never linked; words are not track codes; multi-stop lifts keep every level |
| Unit — engine | `pytest tests/unit/test_impact.py` | 13 | Unknown ≠ available ≠ unavailable; alternative routes; uncertainty propagation; source-inaccessible endpoints; marginal gain; series lifts; exact plan beats greedy; determinism & order invariance; overrides don't mutate baseline |
| Integration — Relate | `pytest tests/integration/test_relate_graph.py` | 19 | Real engine, file stores: persistence after reopen, idempotent import, uniqueness constraint, injection-safe params, transaction rollback, traversal finds both routes, placeholder ends never create routes, non-destructive & reversible scenarios, deterministic persisted analyses, snapshot consistency with history kept, evidence path = route nodes, backup/restore, second writer refused, concurrent HTTP-style access serialised, in-Cypher cross-check agrees with engine |
| Integration — API | `pytest tests/integration/test_api.py` | 9 | Signature flow over HTTP, id validation, 404/422 behaviour, no Cypher endpoint |
| Integration — agent | `pytest tests/integration/test_agent.py` | 5 | Resolver grounded in SERVES edges, abstains on ambiguity/unknown station, reported state; what-if persists nothing; single points of failure; MCP server over stdio on a read-only store rejects writes |
| Unit — region engine | `pytest tests/unit/test_network_engine.py` | 7 | Exact reachability = brute force on 40 random platform subsets; directional quays cut one direction only; riding through a station needs nothing from it; messages grouped per lift; placement by direction and rail station |
| Integration — region | `pytest tests/integration/test_region.py` | 3 | Real store: import, resolver → MATCHES_LIFT, three views with hand-computed counts (12 / 9 / 4), CLOSED from station topology, GHOST verdict, ranking gains, journey verdicts + Relate leg check, region API (422/404), graceful absence |
| Data quality | `pytest tests/data_quality` | 8 | Unique ids, referential integrity, status vocabulary, single snapshot, IDF coordinates, every edge labelled |
| End-to-end | `cd frontend && npx playwright test` | 6 | Select lift → simulate → counts drop → evidence from Relate → top candidate gain = loss → repair view restores counts → export → restore baseline; keyboard access; error states |
| Benchmark | `python scripts/benchmark.py` | — | Timings in docs/BENCHMARK.json |

Last run (2026-11-16, v0.3.0): **74 passed**, **6 e2e passed** on Linux (Python 3.13). v0.2.0's 62 also passed natively on Windows 10 (Python 3.14.4).
Independent check of outage placement / SNCF matching: docs/research/region_eval/.
Evaluation: `python scripts/eval_incidents.py` (incident → lift), `python scripts/agent_eval.py` (agent with/without graph).

Not yet covered: interrupted-import recovery (imports are per-batch
transactions; a crash leaves earlier batches committed, re-running converges by MERGE), 3440×1440 and
tablet screenshots, screen-reader pass.
