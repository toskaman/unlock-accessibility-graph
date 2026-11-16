# Changelog

## 0.2.0 — 2026-11-16
- **Start from an outage report**: free-text report → exact lift via deterministic retrieval over the Relate graph
  (station + IDFM zone names, platforms and spaces each lift SERVES); ambiguous reports return candidates, never a guess.
- **Lifts you can't lose**: single-point-of-failure scan of every working lift (191 of 304).
- **UNLOCK for AI agents**: MCP server (`python -m unlock mcp`) on a read-only store — find_lift, simulate_outage,
  rank_repairs, plan_repairs, critical_lifts, explain_connection, station_overview, cypher_read, network_summary.
- Transient what-if analysis (`POST /api/what-if`) that persists nothing.
- Fix: multi-stop lifts ("Voies F et G / hall / passerelle") now keep every listed level (+51 SERVES edges);
  baseline becomes 1,497 pairs, 582 confirmed.
- Evaluation: incident resolution 21/22 vs 9/22 for text search (`scripts/eval_incidents.py`); agent harness
  `scripts/agent_eval.py` (Claude Code with vs without the graph).
- 62 pytest tests (incl. MCP over stdio), 4 Playwright e2e tests.

## 0.1.1 — 2026-11-16
- Verified natively on Windows 10 (Python 3.14.4): 56 tests, build, serve.
- Narrated 1:38 demo video (Playwright recording of the real app + Kokoro TTS) and README preview GIF.
- Evidence panel moves above the ranking and can be closed; side columns stay in view while scrolling.
- Analyst names the candidate lift instead of its UUID.
- Licence Mobilités reviewed; notice added for the GTFS-derived records.

## 0.1.0 — 2026-11-16
- Data feasibility gate: IDFM elevator data blocked (key), GTFS without lift pathways → SNCF G&C NeTEx + status adopted.
- Source fetcher with sha256 manifest; NeTEx parser; lift-description space derivation with labelled edges.
- Idempotent Relate import (constraints, MERGE, immutable status snapshots) into `database/unlock.rl`.
- Impact engine: three-valued states, four pair classes, scenarios persisted in Relate, ranking, exact k-repair planner.
- Every analysis cross-checked by an independent Cypher query (overrides as a map parameter).
- FastAPI API (localhost, validated ids, no Cypher endpoint) + deterministic UNLOCK Analyst.
- React/MapLibre UI: region map, station cross-section, outage/repair comparison, evidence, graph inspector, export.
- 56 pytest tests (real Relate), 3 Playwright e2e tests, benchmark.
