# Test plan

| Layer | Command | Count | What it proves |
|---|---|---|---|
| Unit — parser | `pytest tests/unit/test_spaces.py` | 10 | Real description strings → correct spaces/derivations; unknown tracks never linked; words are not track codes; multi-stop lifts keep every level |
| Unit — engine | `pytest tests/unit/test_impact.py` | 13 | Unknown ≠ available ≠ unavailable; alternative routes; uncertainty propagation; source-inaccessible endpoints; marginal gain; series lifts; exact plan beats greedy; determinism & order invariance; overrides don't mutate baseline |
| Integration — Relate | `pytest tests/integration/test_relate_graph.py` | 19 | Real engine, file stores: persistence after reopen, idempotent import, uniqueness constraint, injection-safe params, transaction rollback, traversal finds both routes, placeholder ends never create routes, non-destructive & reversible scenarios, deterministic persisted analyses, snapshot consistency with history kept, evidence path = route nodes, backup/restore, second writer refused, concurrent HTTP-style access serialised, in-Cypher cross-check agrees with engine |
| Integration — API | `pytest tests/integration/test_api.py` | 9 | Signature flow over HTTP, id validation, 404/422 behaviour, no Cypher endpoint |
| Integration — agent | `pytest tests/integration/test_agent.py` | 5 | Resolver grounded in SERVES edges, abstains on ambiguity/unknown station, reported state; what-if persists nothing; single points of failure; MCP server over stdio on a read-only store rejects writes |
| Unit — region engine | `pytest tests/unit/test_network_engine.py` | 8 | Exact reachability = brute force on 40 random platform subsets; directional quays cut one direction only; riding through a station needs nothing from it; messages grouped per lift; placement by direction and rail station |
| Unit — IDFM lift status | `pytest tests/unit/test_idfm_lifts.py` | 5 | Level-text classification (line, direction, access, hall); direction placement; station lift graph (chain, redundancy, unknown → DOUBT, rail point with one lift out → DOUBT); night snapshot → UNKNOWN, still out in the morning → UNAVAILABLE; Paris time without tzdata |
| Unit — history | `pytest tests/unit/test_history.py` | 2 | Outage spells (start, end, still out), share out, idempotent appends |
| Unit — second region | `pytest tests/unit/test_regions.py` | 1 | Region network keeps only matched stations, boardability from NeTEx, key-safe ids, patterns cut to the region, ridership by UIC |
| Integration — region | `pytest tests/integration/test_region.py` | 11 | Real store: import, resolver → MATCHES_LIFT, three views with hand-computed counts (12 / 9 / 4), CLOSED from station topology, GHOST verdict, ranking gains, journey verdicts + Relate leg check, region API (422/404), graceful absence; IDFM status replaces PRIM for RATP (CLOSED quay, RATP_LIFT repair, station lift list); rider alerts (OK / CUT, changed flag, trips file rewritten), bulletin (Markdown + script-free HTML), alerts/bulletin API; two regions served side by side (`?region=`); DOUBT where no street route is modelled; RSS/iCalendar feeds (valid XML, folded lines); metrics history + comparison API |
| Static demo engine | `python scripts/check_static_engine.py` | 1,638 | Browser engine (TypeScript) = server engine on the same export: every reach (best, feed; confirmed, possible) and 300 pairs × 2 views (verdict and every leg) |
| Static demo site | `node frontend/scripts/check-static-site.mjs` | 1 | Built site loads, Relate WebAssembly starts, journey + leg re-check, trip alert, reach re-derived, region switch, comparison; no console error |
| Unit — feed watch | `pytest tests/unit/test_feedwatch.py` | 1 | Identical lift content detected across observations; a change is not hidden; re-adding an observation does not double-count |
| Data quality | `pytest tests/data_quality` | 9 | Unique ids, referential integrity, status vocabulary, single snapshot, IDF coordinates, every edge labelled |
| Accessibility | `npx playwright test e2e/a11y.spec.ts` | 2 | axe-core WCAG 2.1 A/AA: no serious/critical violation in region mode, journey result, station card, station mode |
| End-to-end | `cd frontend && npx playwright test` | 9 | Select lift → simulate → counts drop → evidence from Relate → top candidate gain = loss → repair view restores counts → export → restore baseline; keyboard access; error states |
| Benchmark | `python scripts/benchmark.py` | — | Timings in docs/BENCHMARK.json |

Last run (2026-11-17, v0.7.0): **92 passed** on Linux (Python 3.13) and natively on Windows 10 (Python 3.14.4), **10 e2e passed** (incl. accessibility scan and the rider-alert flow) on Linux; region reach re-derived in Cypher for all 519 origins × 3 views (`python scripts/region_crosscheck.py`). v0.2.0's 62 also passed natively on Windows 10 (Python 3.14.4).
Independent check of outage placement / SNCF matching: docs/research/region_eval/.
Evaluation: `python scripts/eval_incidents.py` (incident → lift), `python scripts/agent_eval.py` (agent with/without graph).

Not yet covered: interrupted-import recovery (imports are per-batch
transactions; a crash leaves earlier batches committed, re-running converges by MERGE), 3440×1440 and
tablet screenshots, screen-reader pass.
