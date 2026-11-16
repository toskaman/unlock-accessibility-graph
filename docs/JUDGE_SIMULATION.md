# Internal judge simulation — 16 Nov 2026, after v0.4.0

Internal projections to find weaknesses — **not** a prediction of the jury score. Criteria from the official rules
(5 × equal weight) and the Devpost page (30/25/20/15/10).

## Judge A — product & impact
- **Award:** the first screen answers a question nobody can answer today — *how many step-free journeys does
  Île-de-France really have right now?* — and the journey check speaks to riders directly.
- **Most memorable:** "the outage feed hasn't moved for 38 days; its stale messages hide 96,340 journeys" — a finding
  an operator can act on tomorrow (draft note to PRIM included).
- **Reject:** RATP status only from that same frozen feed; journeys are station pairs, not people.
- **Fix next:** RATP inventory via `etat-des-ascenseurs`; ridership weights if a licensed source exists.

## Judge B — Relate expert
- **Award:** two layers in one store joined by graph structure (`IS_ZONE`, `MATCHES_LIFT`); provenance on every
  derived edge; per-leg Cypher re-checks and geometry from the `NEXT` chain; the station layer still answers with
  `ACYCLIC` QPP traversals and in-Cypher cross-checks.
- **Answered in v0.4.0:** region reach is computed in Python *and* re-derived in Cypher (BFS rounds over
  `HAS_PLATFORM`/`LEG`) — all 519 origins × 3 views agree (`docs/research/region_crosscheck.json`).
- **Reject:** the exact all-pairs count itself is not one Cypher query (path patterns took minutes per pair, D16).

## Judge C — competition & demo
- **Award:** theme fit (connected context makes agents reliable): MCP `check_journey`/`region_overview` on a
  read-only store; independent check of the matching with the bug it found and fixed; runs offline from committed
  snapshots.
- **Reject:** video still shows v0.2.0 until the entrant re-records; small evaluations.
- **Missing:** v0.3.0 video; Devpost form.

## Scorecard A — official rules (1–10, equal weight)
| Criterion | Score | Evidence | Weakness | Best improvement |
|---|---|---|---|---|
| Creativity | 9 | Network-scale journeys + feed reconciliation + station topology + "where can I go from here" map in one graph | — | — |
| Usefulness | 8 | Region repairs, journey check, stale-message list with journeys hidden | RATP redundancy unknown | `etat-des-ascenseurs` key |
| Completeness | 8 | End-to-end, 74 + 6 tests, offline snapshots | v0.3.0 video + Devpost pending | Entrant records/submits |
| Clarity | 8 | Three views side by side, plain verdicts, method on screen | Dense right column | Collapse long messages |
| Connected context (graph, retrieval, agents) | 9.5 | Graph joins two layers + two feeds; resolver over graph; MCP tools; exhaustive Cypher re-derivation | No re-run of the agent eval with region tools | Small agent eval on `check_journey` |

Projection: 42.5 / 50 (35 before v0.2.0, 40 after, 42 at v0.3.0).

## Scorecard B — Devpost weights
| Criterion (weight) | Score /10 | Weighted |
|---|---|---|
| Relate & connected context (30) | 9.5 | 28.5 |
| Functionality & completeness (25) | 8.5 | 21.3 |
| Usefulness (20) | 8 | 16 |
| Documentation & reproducibility (15) | 9 | 13.5 |
| Creativity (10) | 9 | 9 |

Projection: 88.3 / 100 (72.5 → 82.5 → 86.8 → 88.3). Internal estimate, not a jury result.
