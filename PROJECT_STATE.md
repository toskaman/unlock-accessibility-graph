# Project state — 18 Nov 2026

| Item | Status |
|---|---|
| Repository | https://github.com/toskaman/unlock-accessibility-graph (public, branch `main`, topics `relate`, `relate-neo4j-hackathon`) |
| Version | **0.9.0** — two agents, one memory: field reports `(:FieldReport)-[:ABOUT]->(lift)` written through the server, compared with the official status (never changing it), MCP `report_lift` / `field_reports`, agent sessions replayed in the demo, hourly live-demo workflow (repository secrets set 18 Nov; first manual run green); **0.8.1** — whole interface and bulletin in French (EN/FR switch, `?lang=fr`); **0.8.0** — real agent transcript, *History* tab + map replay, welcome card, phone layout, axe-core scan of the deployed demo (0 violations); **0.7.0** — zero-install demo on GitHub Pages (Relate WebAssembly in the browser), every mainland region + comparison, lift-status history (twice a day), trip subscriptions (RSS/calendar), DOUBT where topology is missing; **0.6.0** — fresh RATP lift status (IDFM *État des ascenseurs*) on per-station lift graphs, night-snapshot rule, rider alerts, daily maintenance bulletin, second region (Auvergne-Rhône-Alpes, national data); **0.5.0** — feed watch (repeated identical observations), WCAG 2.1 AA scan of UNLOCK itself, agent eval on region tools; **0.4.0** — step-free reach from any station (Cypher re-derived for all origins), ridership weight; **0.3.0** — whole-region mode (GTFS network + PRIM lift outages in Relate), three views, journey check, region repairs, PRIM-vs-SNCF reconciliation; 0.2.0 station features unchanged |
| Data access | SNCF NeTEx + lift status ✅ public; IDFM ZdC, GTFS, Accessibilité en gare ✅; PRIM traffic messages ✅ with the entrant's token (kept on D:, never committed); IDFM `etat-des-ascenseurs` ✅ with the entrant's Opendatasoft key (kept on D:, never committed); SNCF national GTFS + Fréquentation ✅ public |
| Store | `database/unlock.rl` (~25 MB, single file); clean snapshot `database/snapshot/unlock-snapshot-2026-11-17.rl` |
| Tests | 96 pytest (real Relate, region layer, IDFM lift status, alerts, bulletin, second region, field reports, MCP over stdio) + 13 Playwright e2e (incl. EN/FR switch, field report, agent replay, axe-core a11y, rider alerts); static engine = server engine on 1,038 reaches / 600 journeys |
| Evidence | Region numbers in docs/research/NETWORK_DISCOVERY.md; independent check of outage placement/matching in docs/research/region_eval/ |
| Video | v0.2.0 station-mode video on the v0.2.0 release; the entrant records the new video (script in DEMO_SCRIPT.md, subtitles EN/FR in docs/video/) — run `python -m unlock refresh` in the daytime first |

## Main risks
Night snapshots (SNCF file has no per-lift time) · text-derived topology · RATP lift graph only as good as the level
text · small independent checks (40 + 30 cases) · Devpost form still to submit (entrant).

## Next high-value tasks (ranked)
1. Upload the final video (re-captured on v0.10), add its link and fill the Devpost form from docs/DEVPOST_SUBMISSION.md. — required
2. Check over the next days that the hourly live-demo runs stay green (Actions tab).
3. Stale-feed reports e-mailed to PRIM / IDFM and SNCF Gares & Connexions; waiting for replies. — impact
4. A few real riders (waiting for e-mail replies) try *My usual trips* for a week (alerts vs what they found on site). — evidence
5. Keep the twice-daily history going (Claude reminders) and publish durations / chronic lifts in December. — usefulness
6. Submit a draft on Devpost early: public voting (Popular Choice) is already open and 22 projects are in the gallery. — visibility
