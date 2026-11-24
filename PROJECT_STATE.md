# Project state — 24 Nov 2026

| Item | Status |
|---|---|
| Repository | https://github.com/toskaman/unlock-accessibility-graph (public, branch `main`, topics `relate`, `relate-neo4j-hackathon`) |
| Version | **0.10.1** — survives the 24 Nov 2026 SNCF NeTEx layout change (StopPlace ids lost their INSEE code, lift ids qualified): lift ids normalised to uuid, départements re-derived from national GTFS + UIC + Fréquentation postcode (DRG-checked, ZdC fallback), unmatched places dropped and counted; **0.10.0** — map-first page, plain words, shape-coded stations, list view, easy-read, dark mode, first-visit tour, trip sharing, per-station repair preview; **0.9.0** — two agents, one memory: field reports `(:FieldReport)-[:ABOUT]->(lift)` written through the server, compared with the official status (never changing it), MCP `report_lift` / `field_reports`, agent sessions replayed in the demo, hourly live-demo workflow; **0.8.1** — whole interface and bulletin in French (EN/FR switch, `?lang=fr`); **0.8.0** — real agent transcript, *History* tab + map replay, welcome card, phone layout, axe-core scan of the deployed demo (0 violations); **0.7.0** — zero-install demo on GitHub Pages (Relate WebAssembly in the browser), every mainland region + comparison, lift-status history, trip subscriptions (RSS/calendar), DOUBT where topology is missing; **0.6.0** — fresh RATP lift status (IDFM *État des ascenseurs*), night-snapshot rule, rider alerts, daily maintenance bulletin, second region (national data); 0.2.0–0.5.0 station features, region mode, feed watch, evals unchanged |
| Data access | SNCF NeTEx ✅ public (id layout changed 24 Nov 2026 — handled in 0.10.1) + lift status ✅; IDFM ZdC, GTFS, Accessibilité en gare ✅; PRIM traffic messages ✅ with the entrant's token (kept on D:, never committed); IDFM `etat-des-ascenseurs` ✅ with the entrant's Opendatasoft key (kept on D:, never committed); SNCF national GTFS + Fréquentation ✅ public |
| Store | `database/unlock.rl` (~25 MB, single file); clean snapshot `database/snapshot/unlock-snapshot-2026-11-17.rl` |
| Tests | 108 pytest (real Relate, region layer, IDFM lift status, alerts, bulletin, second region, field reports, MCP over stdio, département recovery) + 14 Playwright e2e (incl. EN/FR switch, field report, agent replay, axe-core a11y, rider alerts); static engine = server engine on 1,038 reaches / 600 journeys |
| Evidence | Region numbers in docs/research/NETWORK_DISCOVERY.md; independent check of outage placement/matching in docs/research/region_eval/ |
| Video | Final film v7 (118 s, EN narration, EN/FR subtitles, thumbnail + poster in video-v3/deliverables/) — QC-measured 24 Nov, awaiting upload; v0.2.0 station-mode video stays on the v0.2.0 release |
| Live demo | Hourly GitHub Actions rebuild (last green 23 Nov 20:09 UTC; 24 Nov runs failed on the NeTEx change, 0.10.1 pushed + workflow re-triggered 24 Nov evening — verify green); history observations committed 21–23 Nov |
| Rules | Re-read in full 24 Nov 2026 (relate.devpost.com, /rules, /updates): no change since 17 Nov; 5 equally weighted criteria, video ≤ 2 min or working demo link, `relate` topic required |

## Main risks
Night snapshots (SNCF file has no per-lift time) · text-derived topology · RATP lift graph only as good as the level
text · small independent checks (40 + 30 cases) · 31 lift-less TER halts + 1 quarantined typo dropped from regions since the NeTEx change (zero lift coverage lost) · Devpost form + video upload still to do (entrant).

## Next high-value tasks (ranked)
1. Upload film v7, add its link and fill the Devpost form from docs/DEVPOST_SUBMISSION.md; submit a draft early (public voting open). — required
2. Watch film v7 once end-to-end before uploading (no human has reviewed the final cut). — required
3. Check over the next days that the hourly live-demo runs stay green (Actions tab).
4. Stale-feed reports e-mailed to PRIM / IDFM and SNCF Gares & Connexions; waiting for replies. — impact
5. A few real riders (waiting for e-mail replies) try *My usual trips* for a week (alerts vs what they found on site). — evidence
6. Publish outage durations / chronic lifts from the history in December. — usefulness
