# Internal judge simulation — 16 Nov 2026 (after P0–P2 + first UI)

These are internal projections to find weaknesses. They are **not** a prediction of the actual jury score.

## Judge A — product & impact
*Strongest reason to award:* turns scattered public lift records into a concrete, inspectable repair priority,
including real lifts out of service today (Mantes-la-Jolie, Noisy-le-Sec).
*Strongest reason to reject:* SNCF stations only, and lift topology comes from free text; "blocked" can't rule
out an undocumented ramp. **Attack:** a judge from RATP would ask about the metro. **Fix:** IDFM key → RATP lifts
(ZdC-level, weaker topology), and a per-station "data confidence" indicator.

## Judge B — Relate expert
*Award:* persistent single-file store; the core answer is a GQL `ACYCLIC` path query; evidence and scenarios are
graph structures; thread-affinity and single-writer limits handled correctly; real-engine tests.
*Reject:* scenario evaluation runs on an in-memory cache of route sets after the traversal — could be read as
"Relate used for loading". **Mitigation in place:** cache is derived only from the Relate query, evidence re-queried
live, inspector shows executed Cypher. **Done:** every analysis now recomputes the affected stations directly in one Cypher query (overrides passed as a
map parameter) and shows "engine = Cypher" in the impact panel; a test asserts agreement.

## Judge C — competition & demo
*Award:* the outage → ranking → evidence → restore loop is visible and numerically consistent (e2e asserts
gain = loss and full restoration).
*Reject:* no video yet; Windows install unverified; repo not yet public with topic `relate`.

## Scorecard A — official rules (5 criteria, equal weight), 1–10

| Criterion | Score | Evidence | Weakness | Best improvement |
|---|---|---|---|---|
| Creativity | 7 | Station cross-section built from lift text; repair ranking with series-lift synergy | Category (accessibility map) is familiar | Lead with "repair together" insight in the demo |
| Usefulness | 6 | Ranks real current outages region-wide | SNCF only; no ridership | RATP via IDFM key; export as planner-ready CSV |
| Completeness | 7 | Full flow, tests, docs, persistence | No video; Windows untested | Record video; Windows check |
| Clarity | 7 | Plain-language UI, legends, methodology | Dense pair grid on big stations | Collapse unchanged pairs by default |
| Connected context | 8 | Path query is the answer; provenance graph; in-Cypher cross-check shown | RATP topology missing | Extend graph to IDFM ZdC-level lifts |

Projection: 35 / 50.

## Scorecard B — Devpost page weights

| Criterion (weight) | Score /10 | Weighted |
|---|---|---|
| Relate & connected context (30) | 8 | 24 |
| Functionality & completeness (25) | 7 | 17.5 |
| Usefulness (20) | 6 | 12 |
| Documentation & reproducibility (15) | 8 | 12 |
| Creativity (10) | 7 | 7 |

Projection: 72.5 / 100.

## Disqualification check
New project (first commit 2026-11-16 ✓), Relate meaningfully used ✓, licences documented ✓,
**public repo + `relate` topic not yet done** (needs the entrant), **video not yet recorded**.
