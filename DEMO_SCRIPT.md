# Demo script v0.8.0 (1:55 — the rules allow up to 2 minutes) — for the entrant to record

**Before recording, in the daytime:** stop the server, run `python -m unlock refresh` (keys from the environment),
then `python -m unlock serve`. Night snapshots show lifts switched off at the end of service; UNLOCK flags them, but
daytime figures make a better video. **Read every number off the screen**; the bracketed figures are those of the
daytime snapshot of 17 Nov 2026, 10:44. The zero-install demo (GitHub Pages) can be filmed instead of the local app for every step
except the agent. Close the 3-line welcome card before recording (or show it for a second at 0:00).

| Time | Screen | Action | Say (suggestion) |
|---|---|---|---|
| 0:00–0:10 | Whole region, *Best available status* | — | "Île-de-France publishes [256,592] step-free station-to-station journeys. With today's lift status, read lift by lift in a Relate graph, [231,883] are confirmed." |
| 0:10–0:20 | Point at the amber card | — | "The official outage feed hasn't changed since 9 October. SNCF's and IDFM's own data contradict it; those stale messages hide [126,628] journeys." |
| 0:20–0:33 | Chip *Rosa Parks → Juvisy*, then *Watch* | *My usual trips* panel | "Can I get there in a wheelchair? And I can watch my daily trip: re-checked against today's lifts, with a step-free detour when my usual route is cut." |
| 0:33–0:42 | Click **Rosa Parks** on the map | The map recolours | "Where can I go from here? [481] stations confirmed — re-derived by Relate with Cypher." |
| 0:42–0:53 | *Repairs that matter* → *Today's maintenance bulletin* | Bulletin tab | "For lift teams: the repair that gives back the most journeys, busiest station first — as a printable bulletin every morning." |
| 0:53–1:05 | *Compare all regions* | Table, then click Occitanie or Grand Est | "The same code on national open data for every region of mainland France. In some regions, barely a third of the published step-free journeys are confirmed today." |
| 1:05–1:20 | Back to Île-de-France: *Replay on the map* under the chart, then the *History* tab | Map breathes observation by observation; chronic lifts | "UNLOCK records the status twice a day: the map replays every observation, and it names the lifts that are out again and again." |
| 1:20–1:40 | Terminal: `claude` with the UNLOCK MCP server | Type « Mon trajet Rosa Parks → Juvisy est-il possible ce matin en fauteuil ? »; let `usual_trip_alert` scroll; the answer | "An AI agent gets the same graph as tools. It answers in French, names the lift at Gare de Lyon and the detour — every fact from the graph, nothing invented." (Speed up the wait ×4; transcript: docs/AGENT_DEMO.md.) |
| 1:40–1:55 | The GitHub Pages demo, banner visible | — | "Try it now, nothing to install: Relate runs in your browser as WebAssembly. UNLOCK — find the repair that unlocks the most journeys." |

If the replay has only a few observations when you record, keep it short and give the spare seconds to the agent.
