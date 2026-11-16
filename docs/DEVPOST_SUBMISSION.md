# Devpost submission — ready to paste

**Project name:** UNLOCK — The Accessibility Impact Graph

**Tagline (elevator pitch):** Which step-free journeys exist in Île-de-France right now, which lift outages cut them — and is the outage data even right? One Relate graph, from the whole network down to a single underpass.

**Repository:** https://github.com/toskaman/unlock-accessibility-graph (topics: `relate`, `relate-neo4j-hackathon`)

**Video (no login needed):** *(v0.3.0 video to be recorded by the entrant — DEMO_SCRIPT.md)*; station-mode video: https://github.com/toskaman/unlock-accessibility-graph/releases/download/v0.2.0/unlock-demo.mp4

**Built with:** relate-db (Relate 1.0.2, embedded, single-file store), Cypher / GQL quantified path patterns, Python, FastAPI, React, TypeScript, Vite, MapLibre GL JS, Playwright, pytest. Open data: SNCF Gares & Connexions (ODbL), Île-de-France Mobilités (Licence Ouverte 2.0, Licence Mobilités), PRIM traffic-information API.

## About the project

### Inspiration
A platform can be "accessible" and still unreachable when one lift breaks. Whether a broken lift matters depends on what else it connects and whether another route exists — information scattered across a NeTEx file, free-text lift locations, an hourly status feed and GTFS.

### What it does
**Whole region.** UNLOCK loads the Île-de-France rail, metro and tram network (996 stations, 59 lines, every
wheelchair-boardable platform) and the lift outages published on PRIM into the same Relate graph, then computes
exactly how many station-to-station journeys are step-free under three views: the published network (256,592), the
best available lift status (192,377) and the PRIM outage feed (88,255). Anyone can ask *can I get from A to B in a
wheelchair?* and get the route, the outages on it and a Relate re-check of every leg. Repairs are ranked by journeys
given back region-wide (top: one lift at La Croix de Berny, +27,156 — the T6/T10 trams' only confirmed connection).

**A real finding.** The PRIM feed's 1,047 lift messages have not changed since 9 Oct 2026, while its other messages
update daily. Reading each SNCF message into the exact lift and comparing with SNCF's hourly feed, UNLOCK finds 235
of 264 contradicted — stale messages that hide 96,340 step-free journeys from apps built on the feed.

**Inside a station.** UNLOCK builds a graph of the 401 SNCF stations in Île-de-France: platforms, underpasses, halls and the 588 lifts that join them, each linked to its latest published status and source file. Select a lift and simulate an outage: UNLOCK shows which step-free platform↔platform and platform↔exit connections break, ranks every possible lift repair across the region by how many confirmed connections it restores (including the lifts really out of service today), and shows the exact graph path and evidence behind each number. Example: at Juvisy-sur-Orge, losing lift ASC3 cuts 21 confirmed connections — a bigger loss than any lift currently out of service in the region.

Three ways in: paste a free-text outage report (UNLOCK resolves it to the exact lift through the graph and refuses to guess when it's ambiguous), browse "lifts you can't lose" (191 single points of failure), or ask an AI agent: the same graph is a read-only MCP server, and in our test Claude Code answered 5/5 planner questions correctly with it and 0/5 without it.

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
The IDFM elevator feed needs an API key and the IDFM GTFS has no lift pathways — the data-feasibility gate forced a switch to SNCF's NeTEx and text-derived topology, with uncertainty made explicit instead of hidden. Relate connections are thread-affine with a single writer, so the API owns the store on one dedicated thread.

### Accomplishments
Whole-region journeys under real outages; a verifiable data-quality finding about the regional lift feed; real current outages ranked region-wide; incident reports resolved 21/22 vs 9/22 for plain text search (0 vs 13 confidently wrong); agent 5/5 with the graph vs 0/5 without; every number traceable to a path and a source hash; 74 tests against the real Relate engine plus 6 end-to-end tests; runs natively on Windows and Linux in seconds.

### What we learned
Accessibility is a property of connections, not of places — and a graph query answers "what does this break?" where a list of lifts cannot.

### What's next
RATP lift inventory and redundancy via IDFM's `etat-des-ascenseurs` (needs an extra key), sending the stale-feed note to PRIM, a per-station data-confidence indicator, and joint "repair together" recommendations for lifts in series.

## Relate capabilities, third-party tools and AI disclosure
- **Relate:** embedded Python API (`relate-db` 1.0.2), single-file persistent store, openCypher with GQL `ACYCLIC` path patterns, uniqueness constraints, range indexes, transactions, map parameters, read-only opens, result summaries.
- **Third-party:** FastAPI, Uvicorn, Pydantic, React, Vite, TypeScript, MapLibre GL JS (OpenFreeMap / OpenStreetMap basemap), Playwright, pytest, ffmpeg; fonts Atkinson Hyperlegible Next and Archivo (OFL).
- **AI:** Code, analysis, docs and the demo video pipeline were produced with Claude Opus 5.5 (Anthropic) as a coding agent, directed by the entrant. Video narration synthesised with the open-weight Kokoro TTS model. The running application uses no AI for its results; an optional rephrasing step (off by default) is rejected if it introduces any number not computed by the engine.
