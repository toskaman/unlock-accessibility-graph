# Project state — 16 Nov 2026

| Item | Status |
|---|---|
| Repository | https://github.com/toskaman/unlock-accessibility-graph (public, branch `main`, topics `relate`, `relate-neo4j-hackathon`) |
| Phases | P0 feasibility ✅ · P1 graph foundation ✅ · P2 impact intelligence ✅ · P3 product experience ✅ (first version) · P4 quality — partly · P5 jury prep — docs, public repo, 1:38 narrated video on release v0.1.0; Devpost form not yet submitted |
| Data access | SNCF NeTEx + lift status ✅ public; IDFM ZdC + GTFS ✅; **IDFM elevators blocked (API key needed)** |
| Store | `database/unlock.rl` (6.4 MB, single file); clean snapshot `database/snapshot/unlock-snapshot-2026-11-16.rl` |
| Tests | 56 pytest passed (real Relate), 3 Playwright e2e passed |
| Demo status | Signature flow works end-to-end on real data (Juvisy-sur-Orge ASC3: −21 confirmed pairs; ranking; evidence; repair restores to 566) |
| Verified on | Linux container (Python 3.13): 56 pytest + 3 e2e. Linux VM on the entrant's PC, project on `Z:\Hackatons\Relate\UNLOCK` (Python 3.10.12, fastapi 0.162.5): 56 pytest passed, `pip install -e .`, `unlock build`, `unlock serve`, outage API + Cypher cross-check OK. Native **Windows 10, Python 3.14.4**: 56 pytest passed, build, serve, outage + cross-check OK (venv on local D:, project on Z: network share). |

## Main risks
SNCF-only coverage · text-derived topology · Devpost form still to submit (entrant).

## Next high-value tasks (ranked)
1. Fill the Devpost form from docs/DEVPOST_SUBMISSION.md (entrant's Devpost account). — required
2. IDFM elevator importer once a key is available (RATP lifts at ZdC level). — usefulness
3. "Repair together" highlight in UI for series lifts (Chelles-Gournay case). — creativity/clarity
4. Collapse unchanged pairs; 3440×1440, tablet and screen-reader passes. — clarity/quality
