# Project contract

**Product.** UNLOCK — The Accessibility Impact Graph. *Find the repair that unlocks the most journeys.*

**User.** Accessibility and maintenance planners at transport operators/authorities (primary);
accessibility researchers and public-interest groups (secondary).

**Job.** Given today's published lift status (or a hypothetical outage), show which step-free connections
inside stations are affected and which lift repair restores the most of them — with path-level evidence.

**Competition.** Relate by Neo4j Hackathon 2026. Contest 11 Nov 2026 18:00 PST → **11 Dec 2026 18:00 PST**
(= 12 Dec 03:00 Paris, CET = UTC+1). Rules list 5 equally weighted criteria (creativity, usefulness,
completeness, clarity, connected context); the Devpost page shows 30/25/20/15/10 — both are tracked,
the rules govern compliance. Requirements: public GitHub repo with topic `relate` (+ `relate-neo4j-hackathon`),
persistent store judges can inspect, README with storage mode, ≤ 2 min video or live demo, AI/tool disclosure.

**Non-negotiables honoured.** Real data only for product numbers (synthetic fixture only in tests);
unknown ≠ accessible; simulations labelled and non-destructive; every edge carries its derivation;
no invented costs/ridership; Relate is the store of record and runs the traversals.

**Out of scope (now).** RATP lifts (needs key), cross-station journey routing, ERP destinations,
public deployment.
