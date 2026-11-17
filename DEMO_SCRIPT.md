# Demo script v0.7.0 (1:55 — the rules allow up to 2 minutes) — for the entrant to record

**Before recording, in the daytime:** stop the server, run `python -m unlock refresh` (keys from the environment),
then `python -m unlock serve`. Night snapshots show lifts switched off at the end of service; UNLOCK flags them, but
daytime figures make a better video. **Read every number off the screen**; the bracketed figures are those of the
committed snapshot. The zero-install demo (GitHub Pages) can be filmed instead of the local app for every step
except the last one.

| Time | Screen | Action | Say (suggestion) |
|---|---|---|---|
| 0:00–0:12 | Whole region, *Best available status* | — | "Île-de-France publishes [256,592] step-free station-to-station journeys. With today's lift status, read lift by lift in a Relate graph, [201,181] are confirmed." |
| 0:12–0:24 | Point at the amber card | — | "The official outage feed hasn't changed since 9 October. SNCF's and IDFM's own data contradict it; those stale messages hide [93,776] journeys." |
| 0:24–0:40 | Chip *Rosa Parks → Juvisy*, then *Watch* | *My usual trips* panel | "Can I get there in a wheelchair? Yes — and I can watch my daily trip: every time I open UNLOCK, or in my calendar, it's re-checked against today's lifts, with a step-free detour when my usual route is cut." |
| 0:40–0:52 | Click **Rosa Parks** on the map | The map recolours | "Where can I go from here? [455] stations confirmed — re-derived by Relate with Cypher." |
| 0:52–1:07 | *Repairs that matter* → *Today's maintenance bulletin* | Bulletin tab | "For lift teams: the repair that gives back the most journeys, busiest station first — as a printable bulletin every morning." |
| 1:07–1:25 | *Compare all regions* | Table, then click Occitanie or Grand Est | "Not an Île-de-France trick: the same code on national open data for every region of mainland France. In some regions, barely a third of the published step-free journeys are confirmed today." |
| 1:25–1:40 | *(optional)* a lift-status history chart, once a few days are recorded | — | "And because UNLOCK records the status twice a day, it shows which lifts are chronically out — not just today." |
| 1:40–1:55 | The GitHub Pages demo, banner visible | — | "Try it now, nothing to install: Relate runs in your browser as WebAssembly. UNLOCK — find the repair that unlocks the most journeys." |

If the history step has nothing to show yet, give its 15 seconds to the region comparison.
