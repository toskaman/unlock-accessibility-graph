# Project state — 16 Nov 2026

| Item | Status |
|---|---|
| Repository | https://github.com/toskaman/unlock-accessibility-graph (public, branch `main`, topics `relate`, `relate-neo4j-hackathon`) |
| Phases | P0 feasibility ✅ · P1 graph foundation ✅ · P2 impact intelligence ✅ · P3 product experience ✅ (first version) · P4 quality — partly · P5 jury prep — docs, public repo, 1:36 narrated video on release v0.2.0; Devpost form not yet submitted |
| Data access | SNCF NeTEx + lift status ✅ public; IDFM ZdC + GTFS ✅; **IDFM elevators blocked (API key needed)** |
| Store | `database/unlock.rl` (6.4 MB, single file); clean snapshot `database/snapshot/unlock-snapshot-2026-11-16.rl` |
| Tests | 62 pytest passed (real Relate, incl. MCP over stdio) on Linux and Windows; 4 Playwright e2e passed |
| Version | 0.2.0 — outage-report resolver, lifts you can't lose, MCP agent server; agent eval 5/5 vs 0/5 |
| Demo status | Signature flow works end-to-end on real data (Juvisy-sur-Orge ASC3: −21 confirmed pairs; ranking; evidence; repair restores to 566) |
| Verified on | v0.2.0: Linux container (Python 3.13) 62 pytest + 4 e2e; native **Windows 10, Python 3.14.4** 62 pytest, build, serve, MCP + Claude Code agent eval (venv on local D:, project on Z: network share). v0.1.0 also passed on a Linux VM with Python 3.10. |

## Main risks
SNCF-only coverage · text-derived topology · Devpost form still to submit (entrant).

## Next high-value tasks (ranked)
1. Fill the Devpost form from docs/DEVPOST_SUBMISSION.md (entrant's Devpost account). — required
2. IDFM elevator importer once a key is available (RATP lifts at ZdC level). — usefulness
3. "Repair together" highlight in UI for series lifts (Chelles-Gournay case). — creativity/clarity
4. Collapse unchanged pairs; 3440×1440, tablet and screen-reader passes. — clarity/quality
