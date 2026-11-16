# Changelog

## 0.4.0 — 2026-11-16
- **Where can I go from here?** Click any station: the map recolours every station of Île-de-France by whether a
  wheelchair user can reach it step-free from there (confirmed / only if listed lifts work / cut by outages / no
  route), with the count, and the daily ticket validations of those stations as a weight.
- **Region numbers re-derived in Cypher.** Each reach is recomputed in Relate by a breadth-first Cypher query over
  `HAS_PLATFORM`/`LEG`; `scripts/region_crosscheck.py` does it for all 519 origins × 3 views — every ordered pair
  agrees with the engine (`docs/research/region_crosscheck.json`).
- Ridership weight: IDFM *Validations sur le réseau ferré* (Q2 2026, Licence Ouverte 2.0) on `NStation`, linked
  `ENTRIES_FROM` its `Dataset`.
- MCP tool `step_free_reach`. Tests 76 + e2e 7.

## 0.3.0 — 2026-11-16
- **Whole region** mode (default): the Île-de-France rail, metro and tram network from IDFM GTFS (996 stations,
  59 lines, 881 wheelchair-boardable platforms) stored in Relate (`NStation`, `NPlatform`, `NLine`, `NPattern`,
  `NEXT`, `LEG`), joined to the SNCF station layer through `IS_ZONE`.
- **Lift outages from PRIM** (token read from env/file, never stored): 356 lifts / 1,047 messages placed on line ×
  platform with a derivation; G&C messages read by the incident resolver into `MATCHES_LIFT` edges.
- **Three views** — published, PRIM feed, best available (SNCF hourly status on station topology + PRIM for RATP);
  exact reachability of all ordered station pairs (~10 ms); confirmed vs possible journeys.
- **Can I get there in a wheelchair?** least-cost journey check compared across the three views, every leg
  re-checked in Cypher, geometry read from the `NEXT` chain.
- **Repairs that matter** region-wide; **Stale messages** (PRIM entries SNCF contradicts, ranked by journeys
  hidden); **Not in the feed**.
- Finding: PRIM lift messages unchanged since 9 Oct 2026; SNCF contradicts 235 of 264 SNCF entries; they hide
  96,340 confirmed journeys. Draft note to IDFM in `docs/research/PRIM_LIFT_FEED_NOTE.md`.
- Independent check of placement/matching (`docs/research/region_eval/`): 3 wrong line placements found → feed
  line links dropped → 0 wrong on re-check; resolver matches 29/30 correct, 0 wrong.
- New sources: IDFM *Accessibilité en gare* (Licence Ouverte 2.0), PRIM *Messages Info Trafic* (Licence Mobilités).
- MCP tools `check_journey`, `region_overview`, `region_repairs`, `station_outages`. 74 tests + 6 e2e.

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
