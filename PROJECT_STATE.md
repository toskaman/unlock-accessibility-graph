# Project state — 16 Nov 2026

| Item | Status |
|---|---|
| Repository | https://github.com/toskaman/unlock-accessibility-graph (public, branch `main`, topics `relate`, `relate-neo4j-hackathon`) |
| Version | **0.3.0** — whole-region mode (GTFS network + PRIM lift outages in Relate), three views, journey check, region repairs, PRIM-vs-SNCF reconciliation; 0.2.0 station features unchanged |
| Data access | SNCF NeTEx + lift status ✅ public; IDFM ZdC, GTFS, Accessibilité en gare ✅; PRIM traffic messages ✅ with the entrant's token (kept on D:, never committed); IDFM `etat-des-ascenseurs` ❌ needs a separate Opendatasoft key |
| Store | `database/unlock.rl` (~25 MB, single file); clean snapshot `database/snapshot/unlock-snapshot-2026-11-16.rl` |
| Tests | 74 pytest (real Relate, region layer, MCP over stdio) + 6 Playwright e2e on Linux; Windows run: see SUBMISSION_CHECKLIST |
| Evidence | Region numbers in docs/research/NETWORK_DISCOVERY.md; independent check of outage placement/matching in docs/research/region_eval/ |
| Video | v0.2.0 station-mode video on the v0.2.0 release; the entrant records the v0.3.0 video (script in DEMO_SCRIPT.md) |

## Main risks
RATP lift status only from the frozen PRIM feed · text-derived topology · small independent checks (40 + 30 cases) ·
Devpost form still to submit (entrant).

## Next high-value tasks (ranked)
1. Record the v0.3.0 video and fill the Devpost form from docs/DEVPOST_SUBMISSION.md. — required
2. Opendatasoft key for `etat-des-ascenseurs` → RATP lift inventory and redundancy (DOUBT → OPEN/CLOSED). — usefulness
3. Send docs/research/PRIM_LIFT_FEED_NOTE.md to PRIM if the entrant agrees. — impact
4. Re-fetch outages close to submission (`python -m unlock fetch-outages`) to show the feed's state that day. — credibility
