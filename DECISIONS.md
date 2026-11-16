# Decisions

| # | Date | Decision | Why | Alternatives rejected |
|---|---|---|---|---|
| D1 | 2026-11-16 | Use SNCF G&C NeTEx + lift status as the lift layer | Public, ODbL, 100 % id join lift↔status, three-valued status, quay-level assessments | IDFM elevator data (needs key); GTFS pathways (no lifts) |
| D2 | 2026-11-16 | Derive lift→space edges from lift location text, label each edge | Only available topology; labelling keeps it honest and auditable | Inventing pathways; geometric proximity |
| D3 | 2026-11-16 | Pairs = platform↔platform and platform↔exit inside a station | Matches what a lift actually enables; bounded and explainable | All node pairs; cross-station journeys (no platform↔line mapping in open data) |
| D4 | 2026-11-16 | Pilot = all SNCF stations in IDF (401), spotlight Juvisy-sur-Orge | Data-dense, bounded, real current KO lifts to rank | A single famous hub chosen for recognisability |
| D5 | 2026-11-16 | Single-file `.rl` store, one owner thread, uvicorn workers=1 | Relate is thread-affine with a single-writer lease | Multi-worker server, separate DB |
| D6 | 2026-11-16 | Cache minimal lift sets per pair after one Relate traversal; evaluate scenarios in pure Python | ms-level scenarios; the traversal and evidence still come from Relate; cache rebuilt from the store | Re-running a 3 s traversal per click |
| D7 | 2026-11-16 | "Blocked" when every modeled route needs an unavailable lift, with explicit scope text | Faithful to modeled criteria; UI states that undocumented ramps could exist | Calling it UNVERIFIED (would hide real outage effects) |
| D8 | 2026-11-16 | Freshness displayed, not folded into classes | Keeps replays reproducible; staleness still visible | Downgrading stale snapshots to UNVERIFIED |
| D9 | 2026-11-16 | No composite score; rank by Δ confirmed pairs only, exact k-repair planner | No verifiable cost/ridership data | Weighted scores |
| D10 | 2026-11-16 | Runtime AI optional and number-validated | Core must work without keys; prevents fabricated figures | Chatbot over raw data |
| D11 | 2026-11-16 | Commit normalized snapshot + snapshot store (ODbL) | Judges can run and inspect offline in seconds | Requiring 130 MB download |
| D12 | 2026-11-16 | Git author set to a neutral local identity | Avoid publishing the entrant's e-mail before they choose an identity | — |
| D13 | 2026-11-16 | Resolve free-text reports deterministically over the graph, abstain when ambiguous | Wrong-but-confident lift ids are the worst failure for a planner; retrieval over SERVES edges is explainable | LLM-only entity extraction |
| D14 | 2026-11-16 | Agent access through MCP on a read-only Relate connection | Relate allows many read-only processes beside the app; the agent can't write even via Cypher | Giving the agent the web API's write endpoints |
| D15 | 2026-11-16 | Keep every level of multi-stop lifts | Text lists 3 levels for some lifts; dropping the 3rd lost real connections | Keep first two sides only (old behaviour) |
| D16 | 2026-11-16 | Region layer from GTFS boardable platforms, journeys = ordered station pairs, exact reachability | Whole-network question needs whole-network data; exact counts keep rankings deterministic | Sampling OD pairs; Relate `SHORTEST` QPP per pair (one pair took > 5 min — Cypher kept for per-leg verification) |
| D17 | 2026-11-16 | A listed outage without topology makes a platform DOUBT, never CLOSED | The PRIM feed carries no redundancy information; inventing it would fake blocked journeys | Treating every listed outage as blocking |
| D18 | 2026-11-16 | Keep three views side by side instead of picking one "truth" | The two official feeds disagree; the disagreement is itself the finding | Silently preferring SNCF |
| D19 | 2026-11-16 | Ignore the feed's own line links when placing an outage | Independent check showed them incomplete (3/40 wrong placements) | Trusting feed links |
| D20 | 2026-11-16 | Boarding point = platform × line | GTFS has one rail platform per station; an RER A lift outage must not close RER D platforms | Platform-level states |
| D21 | 2026-11-16 | PRIM token only from env var / file outside the repo; normalized snapshot (no token) committed | Judges run offline; the secret never leaves the entrant's machine | `.env` in the repo |
| D22 | 2026-11-16 | Region "chokepoints" built, measured and dropped | Only 3 single platforms cut journeys between other stations; impact comes from combinations of outages | Shipping a feature with no signal |
