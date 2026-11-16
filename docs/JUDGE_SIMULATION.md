# Internal judge simulation — 16 Nov 2026, after v0.2.0

Internal projections to find weaknesses — not a prediction of the jury score. Criteria from the official rules
(5 × equal weight) and the Devpost page (30/25/20/15/10). The Neo4j announcement post also stresses "how fully
[entries] use AI and agentic capabilities"; the rules fold agents into *Effective use of connected context*.

## Judge A — product & impact
- **Award:** a planner pastes this morning's outage message and in two clicks sees what it breaks and which repair
  matters most region-wide; the "lifts you can't lose" list is preventive maintenance gold.
- **Reject:** SNCF stations only (no RATP metro); topology derived from text; "blocked" can't exclude undocumented ramps.
- **Most memorable:** a vague report gets "UNLOCK won't guess — pick one".
- **Fix next:** RATP lifts via IDFM key; a held-out evaluation set for the resolver.

## Judge B — Relate expert
- **Award:** the answers *are* graph traversals (ACYCLIC QPP over SERVES), retrieval over graph context
  (zone aliases, SERVES edges) grounds entity resolution, agents get a read-only Relate connection over MCP,
  every analysis re-checked in Cypher, persistent single-file store, real-engine tests incl. MCP over stdio.
- **Reject:** scenario evaluation uses an in-memory route cache (mitigated: derived from Relate, cross-checked, shown).
- **Fix next:** none critical.

## Judge C — competition & demo
- **Award:** theme fit ("connected context makes agents more reliable") demonstrated with a real agent 5/5 vs 0/5;
  clean reproducibility (clone → build → serve, Windows + Linux), narrated video from the real app.
- **Reject:** small evaluation samples (22 reports, 5 agent tasks, single run); resolver tuned on its eval set.
- **Missing:** Devpost form submission (entrant).

## Scorecard A — official rules (1–10, equal weight)
| Criterion | Score | Evidence | Weakness | Best improvement |
|---|---|---|---|---|
| Creativity | 8 | Station cross-section from lift text; repair synergy; refuse-to-guess resolver | Accessibility maps exist | Lead with the outage-report moment (done in video) |
| Usefulness | 7 | Real current outages ranked; SPOF list; free-text intake | SNCF only | RATP via IDFM key |
| Completeness | 8 | End-to-end flows, 62+4 tests, Windows/Linux, video | Devpost form pending | Submit |
| Clarity | 8 | Three entry points, plain language, evidence panel | Dense pair grid on big stations | Collapse unchanged pairs |
| Connected context (graph, retrieval, agents) | 9 | Traversal is the answer; graph retrieval; MCP agent 5/5 vs 0/5 | Small eval | Held-out set, more agent tasks |

Projection: 40 / 50 (was 35 before v0.2.0).

## Scorecard B — Devpost weights
| Criterion (weight) | Score /10 | Weighted |
|---|---|---|
| Relate & connected context (30) | 9 | 27 |
| Functionality & completeness (25) | 8 | 20 |
| Usefulness (20) | 7 | 14 |
| Documentation & reproducibility (15) | 9 | 13.5 |
| Creativity (10) | 8 | 8 |

Projection: 82.5 / 100 (was 72.5).
