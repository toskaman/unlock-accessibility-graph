# Test plan

| Layer | Command | Count | What it proves |
|---|---|---|---|
| Unit — parser | `pytest tests/unit/test_spaces.py` | 9 | Real description strings → correct spaces/derivations; unknown tracks never linked; words are not track codes |
| Unit — engine | `pytest tests/unit/test_impact.py` | 13 | Unknown ≠ available ≠ unavailable; alternative routes; uncertainty propagation; source-inaccessible endpoints; marginal gain; series lifts; exact plan beats greedy; determinism & order invariance; overrides don't mutate baseline |
| Integration — Relate | `pytest tests/integration/test_relate_graph.py` | 19 | Real engine, file stores: persistence after reopen, idempotent import, uniqueness constraint, injection-safe params, transaction rollback, traversal finds both routes, placeholder ends never create routes, non-destructive & reversible scenarios, deterministic persisted analyses, snapshot consistency with history kept, evidence path = route nodes, backup/restore, second writer refused, concurrent HTTP-style access serialised, in-Cypher cross-check agrees with engine |
| Integration — API | `pytest tests/integration/test_api.py` | 9 | Signature flow over HTTP, id validation, 404/422 behaviour, no Cypher endpoint |
| Data quality | `pytest tests/data_quality` | 6 | Unique ids, referential integrity, status vocabulary, single snapshot, IDF coordinates, every edge labelled |
| End-to-end | `cd frontend && npx playwright test` | 3 | Select lift → simulate → counts drop → evidence from Relate → top candidate gain = loss → repair view restores counts → export → restore baseline; keyboard access; error states |
| Benchmark | `python scripts/benchmark.py` | — | Timings in docs/BENCHMARK.json |

Last run (2026-11-16, Linux container, Python 3.13, relate-db 1.0.2): **56 passed**, **3 e2e passed**.

Not yet covered: Windows run of the full suite, interrupted-import recovery (imports are per-batch
transactions; a crash leaves earlier batches committed, re-running converges by MERGE), 3440×1440 and
tablet screenshots, screen-reader pass.
