# Demo script (≤ 2:00) — recorded on the committed snapshot

**Status:** recorded 2026-11-16 → `unlock-demo.mp4` (1:36) on the v0.2.0 release. Fully automated by
`frontend/scripts/record-demo.mjs` (real app, real engine); narration text in `video/narration.json`; see `video/README.md`.

| Time | Screen | Action | Narration (Kokoro TTS) |
|---|---|---|---|
| 0:00–0:07 | Title card | — | "A station can be accessible. Its network may not be. This is UNLOCK…" |
| 0:07–0:21 | Gare du Nord → report box | Type "Juvisy : ascenseur quai 50/51 HS depuis ce matin", **Find the lift** | Lift found in the Relate graph from the station and the platforms it SERVES — no guessing |
| 0:21–0:32 | Juvisy | **Simulate this outage** | Published data untouched; Voies 50/51 cut off; 21 confirmed connections lost |
| 0:32–0:46 | Evidence | Click *Voie 40 ↔ Voie 50* | The actual graph path, two lifts in series, status + source |
| 0:46–0:56 | Ranking | Point at top 3 | ASC3 +21, then lifts really out of service today (+13, +13) |
| 0:56–1:04 | Repair view | Click top candidate | Back to the published state (582); Cypher cross-check = engine |
| 1:04–1:15 | Report + tab | "Ascenseur en panne à Pontoise" → candidates; *Lifts you can't lose* | Never guessed; 191 single points of failure |
| 1:15–1:29 | Agent | Replay of `docs/research/agent_eval/T1-graph.jsonl` | Same graph as a read-only MCP server — an agent answers with real numbers |
| 1:29–1:36 | Title card | — | "UNLOCK doesn't just show you what's broken…" |

All numbers are produced live on snapshot `sncf_lift_status@2273b7c1cb17`. The agent segment is a replay of a
real session's transcript, labelled as such on screen.
