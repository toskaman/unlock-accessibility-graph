# Project state — 17 Nov 2026

| Item | Status |
|---|---|
| Repository | https://github.com/toskaman/unlock-accessibility-graph (public, branch `main`, topics `relate`, `relate-neo4j-hackathon`) |
| Version | **0.7.0** — zero-install demo on GitHub Pages (Relate WebAssembly in the browser), every mainland region + comparison, lift-status history (twice a day), trip subscriptions (RSS/calendar), DOUBT where topology is missing; **0.6.0** — fresh RATP lift status (IDFM *État des ascenseurs*) on per-station lift graphs, night-snapshot rule, rider alerts, daily maintenance bulletin, second region (Auvergne-Rhône-Alpes, national data); **0.5.0** — feed watch (repeated identical observations), WCAG 2.1 AA scan of UNLOCK itself, agent eval on region tools; **0.4.0** — step-free reach from any station (Cypher re-derived for all origins), ridership weight; **0.3.0** — whole-region mode (GTFS network + PRIM lift outages in Relate), three views, journey check, region repairs, PRIM-vs-SNCF reconciliation; 0.2.0 station features unchanged |
| Data access | SNCF NeTEx + lift status ✅ public; IDFM ZdC, GTFS, Accessibilité en gare ✅; PRIM traffic messages ✅ with the entrant's token (kept on D:, never committed); IDFM `etat-des-ascenseurs` ✅ with the entrant's Opendatasoft key (kept on D:, never committed); SNCF national GTFS + Fréquentation ✅ public |
| Store | `database/unlock.rl` (~25 MB, single file); clean snapshot `database/snapshot/unlock-snapshot-2026-11-17.rl` |
| Tests | 92 pytest (real Relate, region layer, IDFM lift status, alerts, bulletin, second region, MCP over stdio) on Linux and Windows + 10 Playwright e2e (incl. axe-core a11y, rider alerts) on Linux; static engine = server engine on 1,038 reaches / 600 journeys |
| Evidence | Region numbers in docs/research/NETWORK_DISCOVERY.md; independent check of outage placement/matching in docs/research/region_eval/ |
| Video | v0.2.0 station-mode video on the v0.2.0 release; the entrant records the new video (script in DEMO_SCRIPT.md) — run `python -m unlock refresh` in the daytime first |

## Main risks
Night snapshots (SNCF file has no per-lift time) · text-derived topology · RATP lift graph only as good as the level
text · small independent checks (40 + 30 cases) · Devpost form still to submit (entrant).

## Next high-value tasks (ranked)
1. `python -m unlock refresh` in the daytime, record the video and fill the Devpost form from docs/DEVPOST_SUBMISSION.md. — required
2. Send docs/research/PRIM_LIFT_FEED_NOTE.md to PRIM (entrant). — impact
3. A few real riders try *My usual trips* for a week (alerts vs what they found on site). — evidence
4. Keep the twice-daily history going (Claude reminders) and publish durations / chronic lifts in December. — usefulness
5. Submit a draft on Devpost early: public voting (Popular Choice) is already open and 22 projects are in the gallery. — visibility
