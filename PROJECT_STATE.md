# Project state — 16 Nov 2026

| Item | Status |
|---|---|
| Branch | `dev/p0-feasibility` (local only; nothing pushed) |
| Phases | P0 feasibility ✅ · P1 graph foundation ✅ · P2 impact intelligence ✅ · P3 product experience ✅ (first version) · P4 quality — partly · P5 jury prep — docs drafted, video/repo pending |
| Data access | SNCF NeTEx + lift status ✅ public; IDFM ZdC + GTFS ✅; **IDFM elevators blocked (API key needed)** |
| Store | `database/unlock.rl` (6.4 MB, single file); clean snapshot `database/snapshot/unlock-snapshot-2026-11-16.rl` |
| Tests | 56 pytest passed (real Relate), 3 Playwright e2e passed |
| Demo status | Signature flow works end-to-end on real data (Juvisy-sur-Orge ASC3: −21 confirmed pairs; ranking; evidence; repair restores to 566) |
| Verified on | Linux container (Python 3.13): 56 pytest + 3 e2e. Linux VM on the entrant's PC, project on `Z:\Hackatons\Relate\UNLOCK` (Python 3.10.12, fastapi 0.162.5): 56 pytest passed, `pip install -e .`, `unlock build`, `unlock serve`, outage API + Cypher cross-check OK. **Native Windows not yet run.** |

## Main risks
Windows-native install unverified · SNCF-only coverage · text-derived topology · video and public repo not yet done.

## Next high-value tasks (ranked)
1. Verify install + tests on the entrant's Windows 10 (`Z:\Hackatons\Relate\UNLOCK`). — blocker risk, low effort
2. Entrant: create the public GitHub repo, add topics `relate` + `relate-neo4j-hackathon`, push. — required, needs authorisation
3. Record the 2-minute video from DEMO_SCRIPT.md. — required
4. IDFM elevator importer once a key is available (RATP lifts at ZdC level). — usefulness
5. "Repair together" highlight in UI for series lifts (Chelles-Gournay case). — creativity/clarity
6. Collapse unchanged pairs; 3440×1440, tablet and screen-reader passes. — clarity/quality
