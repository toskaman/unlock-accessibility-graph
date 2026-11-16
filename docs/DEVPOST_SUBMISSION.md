# Devpost submission — ready to paste

**Project name:** UNLOCK — The Accessibility Impact Graph

**Tagline (elevator pitch):** Find the lift repair that unlocks the most step-free journeys — simulated, ranked and proven on a Relate graph.

**Repository:** https://github.com/toskaman/unlock-accessibility-graph (topics: `relate`, `relate-neo4j-hackathon`)

**Video (no login needed):** https://github.com/toskaman/unlock-accessibility-graph/releases/download/v0.1.0/unlock-demo.mp4

**Built with:** relate-db (Relate 1.0.2, embedded, single-file store), Cypher / GQL quantified path patterns, Python, FastAPI, React, TypeScript, Vite, MapLibre GL JS, Playwright, pytest. Open data: SNCF Gares & Connexions (ODbL), Île-de-France Mobilités (Licence Ouverte 2.0, Licence Mobilités).

## About the project

### Inspiration
A platform can be "accessible" and still unreachable when one lift breaks. Whether a broken lift matters depends on what else it connects and whether another route exists — information scattered across a NeTEx file, free-text lift locations, an hourly status feed and GTFS.

### What it does
UNLOCK builds a graph of the 401 SNCF stations in Île-de-France: platforms, underpasses, halls and the 588 lifts that join them, each linked to its latest published status and source file. Select a lift and simulate an outage: UNLOCK shows which step-free platform↔platform and platform↔exit connections break, ranks every possible lift repair across the region by how many confirmed connections it restores (including the lifts really out of service today), and shows the exact graph path and evidence behind each number. Example: at Juvisy-sur-Orge, losing lift ASC3 cuts 21 confirmed connections — a bigger loss than any lift currently out of service in the region.

### How we built it
- Data: SNCF NeTEx accessibility + hourly lift status (100 % id join), IDFM transfer zones and GTFS lines; every download hashed in a manifest.
- Lift→space edges are derived from the publisher's lift location text ("Voies 50 et 51 / souterrain nord") and each edge carries its derivation label; unmatched text is never linked.
- Relate is the store of record (single `.rl` file). One `ACYCLIC (a)-[:SERVES]-{2,10}(b)` query finds every lift route between station spaces; scenarios are `(:Scenario)-[:OVERRIDES]->(:Lift)`; evidence follows `HAS_STATUS → StatusSnapshot → REPORTED_IN → Dataset(sha256)`.
- A deterministic engine classifies each pair (confirmed accessible / blocked / unverified / out of scope) with three-valued lift status, ranks repairs by marginal gain and finds the exact best set of k repairs. Every analysis is re-computed by an independent Cypher query and the UI shows both agree.

### Challenges
The IDFM elevator feed needs an API key and the IDFM GTFS has no lift pathways — the data-feasibility gate forced a switch to SNCF's NeTEx and text-derived topology, with uncertainty made explicit instead of hidden. Relate connections are thread-affine with a single writer, so the API owns the store on one dedicated thread.

### Accomplishments
Real current outages ranked region-wide; every number traceable to a path and a source hash; 56 tests against the real Relate engine plus end-to-end tests; runs natively on Windows and Linux in seconds.

### What we learned
Accessibility is a property of connections, not of places — and a graph query answers "what does this break?" where a list of lifts cannot.

### What's next
RATP metro/RER lifts via the IDFM key, a per-station data-confidence indicator, and joint "repair together" recommendations for lifts in series.

## Relate capabilities, third-party tools and AI disclosure
- **Relate:** embedded Python API (`relate-db` 1.0.2), single-file persistent store, openCypher with GQL `ACYCLIC` path patterns, uniqueness constraints, range indexes, transactions, map parameters, read-only opens, result summaries.
- **Third-party:** FastAPI, Uvicorn, Pydantic, React, Vite, TypeScript, MapLibre GL JS (OpenFreeMap / OpenStreetMap basemap), Playwright, pytest, ffmpeg; fonts Atkinson Hyperlegible Next and Archivo (OFL).
- **AI:** Code, analysis, docs and the demo video pipeline were produced with Claude Opus 5.5 (Anthropic) as a coding agent, directed by the entrant. Video narration synthesised with the open-weight Kokoro TTS model. The running application uses no AI for its results; an optional rephrasing step (off by default) is rejected if it introduces any number not computed by the engine.
