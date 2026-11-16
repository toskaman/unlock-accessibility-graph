# Internal judge simulation — 16 Nov 2026, after v0.3.0

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
- **Reject:** region reachability is computed in Python over data read from Relate (a Relate `SHORTEST` QPP took
  minutes per pair — documented, D16).
- **Fix next:** a Cypher sample cross-check of region counts on a sub-network.

## Judge C — competition & demo
- **Award:** theme fit (connected context makes agents reliable): MCP `check_journey`/`region_overview` on a
  read-only store; independent check of the matching with the bug it found and fixed; runs offline from committed
  snapshots.
- **Reject:** video still shows v0.2.0 until the entrant re-records; small evaluations.
- **Missing:** v0.3.0 video; Devpost form.

## Scorecard A — official rules (1–10, equal weight)
| Criterion | Score | Evidence | Weakness | Best improvement |
|---|---|---|---|---|
| Creativity | 9 | Network-scale journeys + feed reconciliation + station topology in one graph | — | — |
| Usefulness | 8 | Region repairs, journey check, stale-message list with journeys hidden | RATP redundancy unknown | `etat-des-ascenseurs` key |
| Completeness | 8 | End-to-end, 74 + 6 tests, offline snapshots | v0.3.0 video + Devpost pending | Entrant records/submits |
| Clarity | 8 | Three views side by side, plain verdicts, method on screen | Dense right column | Collapse long messages |
| Connected context (graph, retrieval, agents) | 9 | Graph joins two layers + two feeds; resolver over graph; MCP tools | Region counts in Python | Cypher sample check |

Projection: 42 / 50 (35 before v0.2.0, 40 after).

## Scorecard B — Devpost weights
| Criterion (weight) | Score /10 | Weighted |
|---|---|---|
| Relate & connected context (30) | 9 | 27 |
| Functionality & completeness (25) | 8.5 | 21.3 |
| Usefulness (20) | 8 | 16 |
| Documentation & reproducibility (15) | 9 | 13.5 |
| Creativity (10) | 9 | 9 |

Projection: 86.8 / 100 (72.5 → 82.5 → 86.8).
