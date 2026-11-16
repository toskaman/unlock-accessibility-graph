# Winning Project Intelligence Report

Research date: 16 Nov 2026. Window: Nov 2024 – Nov 2026. Classification: **C** = confirmed by organiser text,
**O** = observed in the write-up, **H** = our reasoned hypothesis. Private jury deliberations are unknown.

## Coverage (honest)

29 award-winning or finalist projects from 7 competitions in 8 domains: graph + agents (Neo4j × 3 events),
multimodal/video, developer AI (Claude Code × 2), consumer AI (Gemini API), vector retrieval (Qdrant), accessibility.
Below the 20-project/8-competition target on competitions (7). Sources are organiser blogs except where noted.

| # | Competition (organiser, date) | Award | Project | What it did | Why it stood out |
|---|---|---|---|---|---|
| 1 | Aura Agent Hackathon (Neo4j, post 7 Jul 2026) | 1st | ConspiracyGraph Agent | Claims, frames, entities, fact-checks (1,282 nodes) on real ClaimReview data | C: "Graph Matters" was the most important criterion; explains *how* claims connect, not true/false |
| 2 | ″ | 2nd | RegulatoryRisk GraphAgent | Regulation→obligation→process graph; 3-hop contagion paths | C: "Regulation networks are inherently graph-shaped" |
| 3 | ″ | 3rd | Korca Triage Agent | Ticket routing on people/skills graph | C: measured top-1 accuracy 72% → 93.4% on 485 tickets |
| 4–6 | ″ | Finalists | Apple HealthGraph Agent, MarketMind, VibeGraph AI | Health data graph; market contagion paths; music graph | C: end-to-end engineering; contagion paths with severity; web design praised |
| 7 | Hack the Video Agent Context Graph (Neo4j/AWS, 31 Jul 2026) | 1st | MealPrep Video Context Graph | Video → ingredient/technique graph + agent | C: "refuses to guess"; reframed as preserving family recipes |
| 8 | ″ | 2nd | Rehearsal | Speaking coach on closed technique ontology | C: model keys not matching a node are discarded — coach can't invent; live demo |
| 9 | ″ | 3rd | ZooVision | Overnight animal-welfare monitor | C: provenance chain, idempotent MERGE, no arbitrary-Cypher endpoint, deterministic severity rules, "most finished thing in the room" |
| 10 | HackwithBay 3.0 (Neo4j blog, 10 Jul 2026) | 1st | VeriGraph | Papers → claims graph; sandboxed experiments write verdicts | C: "verdicts are edges, not fields"; "the model literally cannot write a verdict the numbers don't support" |
| 11 | ″ | 2nd | Constructor | Research assistant, Monte Carlo + Pareto frontier | C: append-only ledger; graph on screen is the one the next analysis reads; nothing faked |
| 12 | ″ | 3rd | Ultra Super Social Passport | Party guests matched via variable-length paths + communities | C: "the graph at its most human" |
| 13 | Gemini API Developer Competition (Google, 21 Nov 2024) | Best overall | Jayu | Assistant acting across apps | C: creative use of visual understanding + UI interaction |
| 14 | ″ | Most impactful + People's choice | Vite Vere | Guidance for people with cognitive disabilities | C: independence / self-reliance |
| 15 | ″ | Most useful | Prospera | Real-time sales coach | O: live, in-the-moment value |
| 16 | ″ | Best Android | Gaze Link | ALS eye-typing + sentence prediction | C: accessible, affordable communication |
| 17 | ″ | Best web | ViddyScribe | Automatic audio description | C: accessibility without disrupting viewing |
| 18 | ″ | Most creative | Outdraw AI | Human-vs-AI drawing game | C: experience "only possible with AI" |
| 19 | Vector Space Hackathon (Qdrant, 29 Sep 2025) | 1st | Vector Vintage | 3D e-commerce exploration (Qdrant + Neo4j) | C: creativity (no project-specific comment) |
| 20 | ″ | 2nd | RoboBank | Robot reflex memory via labelled vectors | O |
| 21 | ″ | 3rd | Spatio-Temporal NPCs | NPC spatial-temporal memory | O |
| 22 | Built with Opus 4.6 (Anthropic, 20 Apr 2026) | 1st | CrossBeam | Permit-process tool by a lawyer | C: domain expert solving their own problem |
| 23 | ″ | Winner | PostVisit.ai | Doctor-to-patient explanations | O |
| 24 | ″ | Winner | Elisa | Hardware coding for kids (1,500+ tests) | C: built in 30 h, 76 commits, >1,500 tests |
| 25 | Built with Opus 4.7 (Anthropic, May/Jun 2026) | 1st | MedKit | Clinical simulator | C: "people closest to a problem build the solution" |
| 26 | AI-Powered DEI Web Accessibility (Hackathon Raptors, 2025) | 1st | VoxSurf | Desktop app for visually impaired users | O |
| 27–28 | ″ / Aura finalists | — | Accessibility Helper (2nd); DrugPath, RecallScope (finalists) | — | O |

## Patterns that transfer to UNLOCK (and what we did)

| Pattern | Evidence | Applied in UNLOCK |
|---|---|---|
| The graph must *be* the intelligence | C (#1, #10, #12) | The answer *is* a path query: series/parallel lifts, single points of failure, repair synergy |
| Agents grounded so they can't invent | C (#8, #10, #9) | MCP tools on a read-only store; resolver returns only existing node ids; Analyst rejects any number not computed |
| Quantified before/after | C (#3) | Incident resolution 21/22 correct, 0 confidently wrong vs text search 9/22, 13 wrong; agent with/without graph (see agent_eval) |
| Refuse to guess, label uncertainty | C (#7) | AMBIGUOUS / UNVERIFIED / OUT_OF_SCOPE are first-class results |
| Provenance + append-only observations | C (#9, #11) | `StatusSnapshot` immutable, `REPORTED_IN → Dataset(sha256)`, scenarios as overlays |
| No arbitrary write endpoint, deterministic rules | C (#9) | No Cypher endpoint in the API; `cypher_read` only on a read-only connection |
| Human reframing | C (#7, #12) | "Find the repair that unlocks the most journeys" — from equipment status to people's journeys |
| Domain expert / real data | C (#22, #25) | Built on official SNCF/IDFM data with a live status feed |
| Finished product, live demo | C (#9, #8) | Runs from a clone in seconds on Windows/Linux; narrated video recorded from the real app |

## Anti-patterns observed
Graph as storage only (C: the Aura write-up says this separated the field); decorative AI; unverifiable impact claims;
demos that can't be reproduced from the README.

## Sources
- https://neo4j.com/blog/developer/what-40-ai-agents-revealed-about-the-future-of-graph-intelligence/ (7 Jul 2026)
- https://neo4j.com/blog/developer/one-starter-repo-three-winners-neo4j-at-hack-the-video-agent-context-graph/ (31 Jul 2026)
- https://neo4j.com/blog/developer/graph-used-right-built-fast-neo4j-at-hackwithbay-3-0/ (10 Jul 2026)
- https://developers.googleblog.com/en/announcing-the-winners-of-the-gemini-api-developer-competition/ (21 Nov 2024)
- https://ai.google.dev/competition
- https://qdrant.tech/blog/vector-space-hackathon-winners-2025/ (29 Sep 2025)
- https://claude.com/blog/meet-the-winners-of-our-built-with-opus-4-6-claude-code-hackathon (20 Apr 2026)
- https://www.edtechinnovationhub.com/news/a-doctor-a-carpenter-and-a-teacher-win-anthropics-global-opus-47-hackathon
- https://ciso2ciso.com/ai-powered-dei-web-accessibility-hackathon-2025-technical-innovations-and-real-world-impact-sourcehackread-com (secondary)
- Relate hackathon announcement (theme, agentic emphasis): https://neo4j.com/blog/graph-database/announcing-the-relate-by-neo4j-hackathon-2026-build-ai-agents-on-an-embedded-graph-database/
