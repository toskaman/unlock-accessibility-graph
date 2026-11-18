# Devpost submission — ready to paste

**Project name:** UNLOCK — The Accessibility Impact Graph

**Tagline (elevator pitch):** Which step-free journeys exist in Île-de-France right now, which lift outages cut them — and is the outage data even right? One Relate graph, from the whole network down to a single underpass.

**Repository:** https://github.com/toskaman/unlock-accessibility-graph (topics: `relate`, `relate-neo4j-hackathon`)

**Try it (no install, no login):** https://toskaman.github.io/unlock-accessibility-graph/ — Relate runs in your browser (WebAssembly) and re-checks every journey and reach.

**Video (no login needed):** *(video to be recorded by the entrant — DEMO_SCRIPT.md)*; station-mode video: https://github.com/toskaman/unlock-accessibility-graph/releases/download/v0.2.0/unlock-demo.mp4

**Built with:** relate-db (Relate 1.0.2, embedded, single-file store), Cypher / GQL quantified path patterns, Python, FastAPI, Relate WebAssembly (@relate/relate-wasm), React, TypeScript, Vite, MapLibre GL JS, Playwright, pytest. Open data: SNCF Gares & Connexions and SNCF Voyageurs (ODbL), Île-de-France Mobilités (Licence Ouverte 2.0, Licence Mobilités: GTFS, lift status, PRIM traffic-information API).

## About the project

### Inspiration
A platform can be "accessible" and still unreachable when one lift breaks. Whether a broken lift matters depends on what else it connects and whether another route exists — information scattered across a NeTEx file, free-text lift locations, an hourly status feed and GTFS.

### What it does
**Whole region.** UNLOCK loads the Île-de-France rail, metro and tram network (996 stations, 60 lines, every
wheelchair-boardable platform), the status of all 986 lifts (SNCF hourly feed + IDFM's lift-status dataset, read on
per-station lift graphs) and the lift outages published on PRIM into the same Relate graph, then computes exactly how
many station-to-station journeys are step-free under three views: the published network (256,592), the best
available lift status (231,883 on 17 Nov, 10:44) and the PRIM outage feed (88,255). Click any station and the whole
map shows where a wheelchair user can go from there (Rosa Parks: 481 stations confirmed, 294 if you believe the feed),
each reach re-derived in Cypher. Anyone can ask *can I get from A to B in a wheelchair?* and get the route, the
outages on it and a Relate re-check of every leg. Repairs are ranked by journeys given back region-wide, ties broken by
how busy the station is (top: Paris Gare du Nord's Transmanche lift).

**For riders: "is my usual trip still step-free today?"** Watch a trip; each visit re-checks it against today's lift
status — step-free / detour needed (with the detour) / at risk / cut, and which lift is responsible. Trips stay in
the rider's browser; the same check runs from the command line for a daily scheduled alert, or through MCP.

**For lift teams: a daily bulletin** generated from the graph — repairs that give back the most journeys, stations cut
off and their lifts, changes since the previous fetch, statuses to check on site, passenger messages to correct.

**Every region of mainland France.** The same code runs on the 11 other mainland regions from national open data
only (SNCF NeTEx, SNCF hourly status, SNCF national timetable, station ridership), with a side-by-side comparison and
a per-region quality column. Generalising found two problems that also affected Île-de-France — a lift-text parsing
bug and outages silently ignored at stations whose text names no exit — both fixed.

**Two AI agents, one memory.** The graph is exposed to AI agents through MCP. A real, unedited session: a wheelchair
user tells Claude « l'ascenseur du quai des voies 50/51 à Juvisy est en panne » — the agent resolves the sentence to
one lift in the graph and writes a field report into Relate. A second agent, in a new session, for the maintenance
team, reads it back: the report contradicts SNCF's hourly status (*available*) but agrees with IDFM's dataset (*out
of service* since the day before), so it says: check Juvisy ASC3 first. Reports never change the official status or
any count. Riders can report from the web page too, and the demo replays these sessions step by step (*Ask an AI agent*).

**History.** UNLOCK records the lift status: how long outages last, which lifts are chronically out, how
many step-free journeys each region loses day after day. The *History* tab ranks the lifts that are out again and
again, and *Replay on the map* steps the region map through every recorded observation.

**Try it without installing anything, in English or French.** Rebuilt every hour from the live lift status by GitHub
Actions. The GitHub Pages demo loads the graph exported from the Relate store into
Relate's WebAssembly build in the visitor's browser, which re-runs the server's own Cypher to re-check every journey
leg and every reach (the browser engine was checked identical to the server's on 1,038 reaches and 600 journeys).

**A real finding.** The PRIM feed's 1,047 lift messages have not changed since 9 Oct 2026, while its other messages
update daily (five fetches over 15 hours: byte-identical lift content). Reading each SNCF message into the exact lift
and comparing with SNCF's hourly feed, UNLOCK finds 216 of 264 contradicted; IDFM's own lift-status dataset contradicts
37 of the 39 RATP messages it can be matched to — stale messages that hide 126,628 step-free journeys from apps built on
the feed.

**Inside a station.** UNLOCK builds a graph of the 401 SNCF stations in Île-de-France: platforms, underpasses, halls and the 588 lifts that join them, each linked to its latest published status and source file. Select a lift and simulate an outage: UNLOCK shows which step-free platform↔platform and platform↔exit connections break, ranks every possible lift repair across the region by how many confirmed connections it restores (including the lifts really out of service today), and shows the exact graph path and evidence behind each number. Example: at Juvisy-sur-Orge, losing lift ASC3 cuts 21 confirmed connections — a bigger loss than any lift currently out of service in the region.

Three ways in: paste a free-text outage report (UNLOCK resolves it to the exact lift through the graph and refuses to guess when it's ambiguous), browse "lifts you can't lose" (213 single points of failure), or ask an AI agent: the same graph is a read-only MCP server, and in our test Claude Code answered 7 of 8 planner and rider questions correctly with it and 0/8 without it. A published, unedited transcript shows it answering a wheelchair user in French — « Rosa Parks → Juvisy ce matin ? » — with the detour and the exact lifts at fault, every fact from one tool call.

### How we built it
- Region: GTFS stops/patterns → `NStation`, `NPlatform`, `NEXT`, `LEG` in Relate; PRIM messages → `LiftOutage
  -[:AFFECTS {derivation}]->NPlatform`; the incident resolver writes `MATCHES_LIFT` to SNCF lifts; exact reachability of
  all ordered station pairs (SCC + bitsets, ~10 ms); an independent agent checked 40 placements and 30 matches (0 wrong
  after one fix).
- Data: SNCF NeTEx accessibility + hourly lift status (100 % id join), IDFM transfer zones and GTFS lines; every download hashed in a manifest.
- Lift→space edges are derived from the publisher's lift location text ("Voies 50 et 51 / souterrain nord") and each edge carries its derivation label; unmatched text is never linked.
- Relate is the store of record (single `.rl` file). One `ACYCLIC (a)-[:SERVES]-{2,10}(b)` query finds every lift route between station spaces; scenarios are `(:Scenario)-[:OVERRIDES]->(:Lift)`; evidence follows `HAS_STATUS → StatusSnapshot → REPORTED_IN → Dataset(sha256)`.
- A deterministic engine classifies each pair (confirmed accessible / blocked / unverified / out of scope) with three-valued lift status, ranks repairs by marginal gain and finds the exact best set of k repairs. Every analysis is re-computed by an independent Cypher query and the UI shows both agree.

### Challenges
The IDFM GTFS has no lift pathways — the data-feasibility gate forced a switch to SNCF's NeTEx and text-derived topology, with uncertainty made explicit instead of hidden. IDFM's lift-status dataset reports lifts switched off for the night as failures: a night snapshot first showed 188 RATP "outages", 163 of them switched off after midnight — UNLOCK now counts those as unknown instead of inventing 100+ repairs. Relate connections are thread-affine with a single writer, so the API owns the store on one dedicated thread.

### Accomplishments
Whole-region journeys under real outages; a verifiable data-quality finding about the regional lift feed; real current outages ranked region-wide; incident reports resolved 21/22 vs 9/22 for plain text search (0 vs 13 confidently wrong); agent 7/8 with the graph vs 0/8 without (eight station- and region-level questions, both rounds published); every number traceable to a path and a source hash; 96 tests against the real Relate engine plus 13 end-to-end tests (incl. a WCAG 2.1 AA scan of UNLOCK itself, and an axe-core scan of the deployed demo on desktop and phone); every region reach re-derived in Cypher for all 519 origins × 3 views with zero disagreement; runs natively on Windows and Linux in seconds.

### What we learned
Accessibility is a property of connections, not of places — and a graph query answers "what does this break?" where a list of lifts cannot.

### What's next
Real riders trying the trip alerts for a week; three weeks of lift-status history turned into outage durations and chronic-lift lists; sending the stale-feed note to PRIM; joint "repair together" recommendations for lifts in series.

## Relate capabilities, third-party tools and AI disclosure
- **Relate:** embedded Python API (`relate-db` 1.0.2), single-file persistent store, openCypher with GQL `ACYCLIC` path patterns, uniqueness constraints, range indexes, transactions, map parameters, read-only opens, result summaries.
- **Third-party:** FastAPI, Uvicorn, Pydantic, React, Vite, TypeScript, MapLibre GL JS (OpenFreeMap / OpenStreetMap basemap), Playwright, pytest, ffmpeg; fonts Atkinson Hyperlegible Next and Archivo (OFL).
- **AI:** Code, analysis, docs and the demo video pipeline were produced with Claude Opus 5.5 (Anthropic) as a coding agent, directed by the entrant. Video narration synthesised with the open-weight Kokoro TTS model. The running application uses no AI for its results; an optional rephrasing step (off by default) is rejected if it introduces any number not computed by the engine.
