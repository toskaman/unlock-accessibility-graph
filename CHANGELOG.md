# Changelog

## 0.8.0 — 2026-11-17
- **Ask an agent — a real transcript** (docs/AGENT_DEMO.md, `scripts/agent_demo.py`): Claude Code in headless mode,
  with UNLOCK's MCP tools as its only tools, answers a wheelchair user in French (« Rosa Parks → Juvisy ce matin ? »:
  detour via Neuilly – Porte Maillot, the three lifts at Gare de Lyon, the time the status was read) and a
  maintenance planner. Unedited apart from local paths; raw JSON published. MCP instructions now point riders to
  `usual_trip_alert` and planners to `maintenance_bulletin`.
- **History you can see.** *History* tab: lifts ranked by share of daytime observations out of service, *chronic*
  flagged (≥ 30 % over ≥ 7 days), out since, IDFM's last status change. **Replay on the map**: the region map steps
  through the recorded observations (stations cut / in doubt). New `GET /api/region/history/lifts` and
  `/api/region/history/timelapse`; the zero-install demo re-exports them at every collection, so it shows the history
  gathered so far.
- **Welcome card** (3 lines, dismissible, remembered in the browser): what UNLOCK answers and where to start.
- **Phones and accessibility.** One-column layout with no horizontal scroll on phones (390 px); axe-core scan of the
  deployed demo (`frontend/scripts/check-static-a11y.mjs`, WCAG 2.0/2.1 A+AA, desktop + iPhone 13, home and
  journey+history views). Fixed: the *Remove* button's accessible name now contains its visible label.
- e2e: the stale-message drill-down accepts either an SNCF or a RATP lift (the first stale message changes with the
  data). Tests: 94 pytest + 10 e2e.

## 0.7.0 — 2026-11-17
- **Zero-install demo** on GitHub Pages (https://toskaman.github.io/unlock-accessibility-graph/): region mode for
  every region, journeys, reach, trip alerts, comparison and bulletin, on a snapshot exported from the Relate stores
  (`scripts/export_static.py`). Journeys and reaches are computed in the browser by a port of the server engine —
  checked identical on 1,038 reaches and 600 journeys (`scripts/check_static_engine.py`) — and every leg and reach is
  re-checked by **Relate compiled to WebAssembly** (`@relate/relate-wasm` 1.0.2, in a worker) with the server's own
  Cypher. Clearly labelled as a snapshot; station mode and simulations stay in the installed app (D33).
- **Every region of mainland France** from national SNCF data (`python -m unlock build-region all`, ~1 min): 11
  regions besides Île-de-France, region picker, *Compare all regions* table, `GET /api/regions/compare`,
  `scripts/regions_report.py` (with a per-region topology-coverage column and a list of weak station matches).
- **Honest where the topology is missing** (D31): a lift not reported working at a station whose lift text gives no
  platform↔street route now puts the station's rail points in DOUBT instead of being ignored. Île-de-France best view:
  201,181 confirmed journeys (was 207,509 with the same status).
- **Lift-status history** (`python -m unlock record`, run by `refresh`): national SNCF status per file version,
  headline metrics and non-open stations per region per observation; spells / chronic-lift analyses; history chart
  in the region view once two observations exist; `GET /api/region/history`. Collected twice a day in the daytime,
  semi-automatically (D34, docs/HISTORY.md).
- **Subscribe to a trip** — RSS and iCalendar links per watched trip, stateless (`/api/region/trips/feed.rss|ics`).
- Station cards outside IDF list the station's SNCF lifts with their hourly status.
- Building several regions in one process parses NeTEx and the national GTFS once (cached).
- Demo script cut to 1:55 (the rules allow up to 2 minutes).
- Tests: 92 pytest + 10 e2e; static-site smoke test (`frontend/scripts/check-static-site.mjs`).

## 0.6.0 — 2026-11-17
- **Fresh RATP lift status.** IDFM *État des ascenseurs* (986 lifts, 3 updates a day, free Opendatasoft key —
  created on the entrant's account, stored outside the repo) imported as `(:IdfmLift)` with the levels each lift
  joins (`CONNECTS` to boarding points, `SAME_LIFT` to the 566 SNCF lifts of the station layer, `REPORTS_ON` from
  39 PRIM messages). Per-station RATP lift graph (street ↔ halls ↔ platforms): RATP points can now be CLOSED, not
  only DOUBT. The best view no longer uses the frozen PRIM messages. Snapshot 17 Nov 01:26 Paris: best view
  **207,509** confirmed journeys of 256,592 (252,556 possible); IDFM contradicts 18 of the 39 RATP messages it can
  be matched to.
- **Night snapshots handled honestly**: lifts switched off since 23:00 in a night snapshot are UNKNOWN
  (`NIGHT_CLOSURE_SUSPECTED`), not outages (166 on 17 Nov 01:26); the UI, bulletin and MCP say so (D26).
- **Rider alerts** ("is my usual trip still step-free today?"): *Watch* a checked journey (kept in the browser),
  `POST /api/region/trips/check`, `python -m unlock alerts trips.json` for a scheduled check, MCP
  `usual_trip_alert`. Statuses OK / DETOUR (with the detour) / AT_RISK / CUT / NO_STEP_FREE_ROUTE.
- **Daily maintenance bulletin**: `python -m unlock bulletin`, `/api/region/bulletin(.html)`, MCP
  `maintenance_bulletin` — repairs ranked by journeys given back (ties: busiest station), *check first* list,
  stations cut off and their lifts, changes since the previous lift-status fetch (`(:LiftStatusObservation)`),
  messages to correct.
- **Second region — Auvergne-Rhône-Alpes** from national data only (SNCF NeTEx, SNCF hourly status, SNCF national
  GTFS, *Fréquentation en gares*): `python -m unlock build-region ara`, region picker in the UI, `?region=ara` on
  every region endpoint. 327 stations, 51 declared wheelchair-accessible, 2,070 of 2,550 step-free journeys
  confirmed on 17 Nov. Same engine, store layout and tests.
- **Parser fix found while generalising** (D30): « Voies A et S » lost track A (read as "à"), and an exit named
  beside a track (« Hall et Voies A et S ») was dropped. Île-de-France station layer: +54/−11 SERVES edges,
  1,662 pairs (was 1,497), 653 confirmed, 213 single points of failure (was 191).
- `python -m unlock refresh` (SNCF + PRIM + IDFM status, rebuild every region); `fetch-lifts`.
- Repairs with equal gains ordered by daily station use (D28). `fetch_sources.py` reads/writes the manifest as
  UTF-8 (Windows wrote cp1252).
- Tests: 87 pytest + 10 Playwright e2e (new: IDFM parsing and station lift graph, night rule, rider alerts,
  bulletin, multi-region API, second-region builder, rider-alert UI flow).

## 0.5.0 — 2026-11-17
- **Feed watch**: every `fetch-outages` appends one observation (time, counts, last lift update, SHA-256 of all lift
  messages) to `data/normalized/outage_feed_history.json`, imported as `(:FeedObservation)` nodes. Three fetches
  (16 Nov 19:13, 22:33, 23:14 UTC) returned byte-identical lift content; the UI and MCP say so.
- **Accessibility of UNLOCK itself**: axe-core WCAG 2.1 A/AA scan in e2e (region mode, journey result, station card,
  station mode) — fixed colour contrast (`--ink-3`, amber text) and map containers (`role="region"` instead of
  `img` around interactive canvases). 0 serious/critical violations.
- **Agent eval extended to the region layer** (T6–T8): 7/8 with the graph across all tasks vs 0/8 without; round 1
  exposed two tool-output gaps (`step_free_reach` now explains doubts at the origin, `region_overview` returns
  engine-computed `key_facts`), fixed and re-run — both rounds published (AGENT_EVAL.md).
- JSON outputs always written with LF line endings (Windows fetches no longer churn diffs).

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
