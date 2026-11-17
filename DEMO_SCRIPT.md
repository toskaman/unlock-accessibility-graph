# Demo script v0.6.0 (≤ 2:30) — for the entrant to record

The v0.2.0 station-mode video (1:36) is on the v0.2.0 release and was produced by
`frontend/scripts/record-demo.mjs`. This script is for the new video.

**Before recording, in the daytime:** stop the server, run `python -m unlock refresh` (keys from the environment),
then `python -m unlock serve`. The committed snapshot was taken at night (17 Nov, 01:26 Paris), when many lifts are
switched off — UNLOCK flags that on screen, but daytime figures make a better video. **Read every number off the
screen**; the figures in brackets are those of the committed snapshot.

| Time | Screen | Action | Say (suggestion) |
|---|---|---|---|
| 0:00–0:12 | Whole region, *Best available status* | — | "Île-de-France publishes [256,592] step-free station-to-station journeys. With today's lift status — SNCF's hourly feed and IDFM's own lift data, read lift by lift — [207,509] are confirmed." |
| 0:12–0:27 | Click *PRIM outage feed* | Point at the amber card | "Believe the regional outage feed and it drops to [88,255]. Its 1,047 lift messages haven't changed since 9 October. SNCF's own data says [225] of its [264] SNCF lifts work, IDFM's says [18] of [39] RATP ones do. Those stale messages hide [93,776] journeys." |
| 0:27–0:47 | Chip *Rosa Parks → Juvisy* | Legs, then the mini-verdicts | "Can I get there in a wheelchair? With the best status: yes — RER E, then RER C. With the feed: only if 11 listed lifts work. Every leg is re-checked in the Relate graph." |
| 0:47–1:02 | *Watch Rosa Parks → Juvisy* | *My usual trips* panel | "I do this trip every day. Watch it: every time I open UNLOCK it's re-checked against today's lifts — and if my usual route is cut, it gives me the step-free detour. It stays in my browser; the same check runs as a daily command." |
| 1:02–1:17 | Click **Rosa Parks** on the map | The map recolours | "Where can I go from here? [455] stations, confirmed — re-derived in Cypher. With the feed: [294]." |
| 1:17–1:35 | *Repairs that matter* → *Today's maintenance bulletin* | Bulletin opens in a new tab | "For the lift teams: one repair usually gives a whole station back to the network; ties go to the busiest station. Every morning, this page: fix first, stations cut off, what changed overnight, what to check on site, which messages to correct." |
| 1:35–1:55 | Region picker → *Auvergne-Rhône-Alpes* | Chip *Lyon Gorge de Loup → Lyon Part Dieu* | "Not an Île-de-France trick: the same code on national SNCF data. Auvergne-Rhône-Alpes: [2,070] of [2,550] journeys confirmed, and Gorge de Loup to Part-Dieu is cut today by one lift." |
| 1:55–2:10 | Back to Île-de-France, click a SNCF station → *Open inside the station* | Station cross-section | "Down to a single underpass: the same graph holds every lift, platform and route inside 401 SNCF stations." |
| 2:10–2:25 | *Inspect the graph* | — | "Two regions, 986 lift statuses, 356 outage messages — each in one Relate file, every number traceable. UNLOCK: find the repair that unlocks the most journeys." |
