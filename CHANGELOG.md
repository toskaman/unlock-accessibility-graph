# Changelog

## 0.1.0 — 2026-11-16
- Data feasibility gate: IDFM elevator data blocked (key), GTFS without lift pathways → SNCF G&C NeTEx + status adopted.
- Source fetcher with sha256 manifest; NeTEx parser; lift-description space derivation with labelled edges.
- Idempotent Relate import (constraints, MERGE, immutable status snapshots) into `database/unlock.rl`.
- Impact engine: three-valued states, four pair classes, scenarios persisted in Relate, ranking, exact k-repair planner.
- Every analysis cross-checked by an independent Cypher query (overrides as a map parameter).
- FastAPI API (localhost, validated ids, no Cypher endpoint) + deterministic UNLOCK Analyst.
- React/MapLibre UI: region map, station cross-section, outage/repair comparison, evidence, graph inspector, export.
- 56 pytest tests (real Relate), 3 Playwright e2e tests, benchmark.
