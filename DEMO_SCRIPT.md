# Demo script (≤ 2:00) — recorded on the committed snapshot

Setup: `python -m unlock serve`, browser at 1920×1080, `http://127.0.0.1:8000/#station=Juvisy-sur-Orge`.
Reset between takes: **Restore published status** (or restart the server).

| Time | Screen | Action | Caption / narration |
|---|---|---|---|
| 0:00–0:08 | Region map + Juvisy cross-section | none | "A station can be accessible. Its network may not be." |
| 0:08–0:22 | Cross-section | Click lift **ASC3 — Voies 50 et 51 / souterrain nord** | "Published status: working. 21 modeled connections depend on it." |
| 0:22–0:40 | Whole UI | Click **Simulate outage** | "Simulated — the published observation is unchanged. Voie 50 and 51 are cut off: 21 confirmed connections become blocked." |
| 0:40–0:60 | Evidence panel | Click *Voie 40 ↔ Voie 50* | "This is the actual path in Relate: Voie 40 → ASC8 → souterrain nord → ASC3 → Voie 50 — two lifts in series." |
| 0:60–0:82 | Ranking | Point at the list | "Every out-of-service lift in Île-de-France, ranked by connections restored: ASC3 +21, Mantes-la-Jolie +13, Noisy-le-Sec +13 — the last two are out of service right now." |
| 0:82–1:40 | Repair view | Click the top candidate; toggle Published / Outage / Repair | "With the repair, confirmed connections return to 566 — exactly the baseline." |
| 1:40–1:52 | Inspector | Click **Inspect the graph** | "One Relate file: 6,077 nodes, 11,680 relationships, the ACYCLIC path query, and the statements it just ran." |
| 1:52–2:00 | Title | — | "UNLOCK doesn't just show you what's broken. It shows you what fixing it makes possible." |

All numbers above are produced live by the engine on snapshot `sncf_lift_status@2273b7c1cb17`; re-check them
after any data refresh. Do not present the recording as live interaction.
