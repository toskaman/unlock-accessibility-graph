# Demo script v0.3.0 (≤ 2:00) — for the entrant to record

The v0.2.0 station-mode video (1:36) is on the v0.2.0 release and was produced by
`frontend/scripts/record-demo.mjs`. This script is for the new whole-region video. All numbers below are from
the committed snapshot (PRIM feed observed 16 Nov 2026 22:33 UTC, SNCF status `sncf_lift_status@2273b7c1cb17`);
if you run `fetch-outages` before recording, read the numbers off the screen instead.

| Time | Screen | Action | Say (suggestion) |
|---|---|---|---|
| 0:00–0:10 | Whole region, *Best available status* | — | "Île-de-France publishes 256,592 step-free station-to-station journeys. With today's lift outages, 192,377 are confirmed." |
| 0:10–0:25 | Click *PRIM outage feed* | Point at the amber card | "Believe the regional outage feed and it drops to 88,255. But its 1,047 lift messages haven't changed since 9 October — 38 days — and SNCF's own hourly data says 235 of its 264 SNCF lifts work. Those stale messages alone hide 96,340 journeys." |
| 0:25–0:50 | Chip *Rosa Parks → Juvisy* | Show legs, then the three mini-verdicts | "Can I get there in a wheelchair? With the best status: yes — RER E, then RER C. With the feed: only if 11 listed lifts work. Every leg is re-checked in the Relate graph." |
| 0:50–1:10 | Click **Rosa Parks** on the map | The whole map recolours | "Where can I go from here? 437 stations, confirmed — re-derived in Cypher, 437 = 437. Switch to the feed: 294." |
| (alt) | *Stale messages* → first item | Station card | "Rosa Parks: PRIM lists a broken lift; UNLOCK read the message, matched the SNCF lift, and SNCF says it works. Correcting that one message gives back 10,030 journeys." |
| 1:10–1:30 | *Best available status* → *Repairs that matter* | Click La Croix de Berny | "Region-wide, the repair that matters most: one lift at La Croix de Berny. With Viroflay's lift also listed out since last November, the T6 and T10 trams lose their only confirmed step-free connections — 27,156 journeys." |
| 1:30–1:45 | Click a SNCF station → *Open inside the station* | Station cross-section | "And down to a single underpass: the same graph holds every lift, platform and route inside 401 SNCF stations." |
| 1:45–2:00 | *Inspect the graph* | — | "996 stations, 14,000 rides, 356 outages, 588 lifts — one Relate file, every number traceable. UNLOCK: find the repair that unlocks the most journeys." |
