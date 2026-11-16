# Methodology — what UNLOCK calculates, exactly

Algorithm version: `unlock-impact/1.0` (persisted on every `Scenario` and `AnalysisResult`).

## 1. Units of analysis

**Space** — a place inside one station that a lift connects: a platform (one per NeTEx quay, e.g. *Voie 50*),
a connector (*souterrain*, *passerelle*, *mezzanine*…), an exit/hall (*hall*, *parvis*, *sortie…*), or a
text-only platform that could not be matched to a quay. Spaces come from splitting each lift's
published location text on `/` (see `backend/unlock/ingest/spaces.py`). Identical normalised names in the
same station are one space (labelled `NAMED_SPACE`).

**Origin–destination pair** — an unordered pair of *anchor* spaces in the same station:
platform ↔ platform, or platform ↔ exit (exit ↔ exit is excluded). 1,497 pairs in the pilot.
A pair counts a *modeled connection*, never a number of people.

**Route** — an acyclic path in Relate `(:Space)<-[:SERVES]-(:Lift)-[:SERVES]->(:Space)…` of at most
5 lifts between the two anchors, found with one Cypher query:

```cypher
MATCH (st:Station)-[:HAS_SPACE]->(a:Space) WHERE a.role IN $roles
MATCH (st)-[:HAS_SPACE]->(b:Space) WHERE b.role IN $roles AND a.id < b.id AND NOT (a.role='EXIT' AND b.role='EXIT')
OPTIONAL MATCH p = ACYCLIC (a)-[:SERVES]-{2,10}(b)
RETURN st.id, a.id, b.id, [n IN nodes(p) | n.id] AS nodes, [n IN nodes(p) WHERE n:Lift | n.id] AS lifts
```

Only routes with a *minimal* lift set are kept (a route needing {A,B,C} can never be usable when the
route needing {A,B} is not, so it never changes a classification).

## 2. Two separate dimensions

| Dimension | Values | Source |
|---|---|---|
| Physical accessibility (endpoint) | ACCESSIBLE · INACCESSIBLE · UNKNOWN · NOT_APPLICABLE | NeTEx `Quay/AccessibilityAssessment/…/StepFreeAccess` via `(:AccessibilityAssertion)-[:ABOUT]->(:Quay)`; exits are NOT_APPLICABLE; text-only platforms are UNKNOWN |
| Equipment status (lift) | AVAILABLE · UNAVAILABLE · UNKNOWN | SNCF status feed OK / KO / INCONNU via `(:Lift)-[:HAS_STATUS]->(:StatusSnapshot)`; a lift with no observation in the snapshot is UNKNOWN |

A **route** is AVAILABLE only if every lift on it is AVAILABLE; any UNAVAILABLE lift makes it
UNAVAILABLE; otherwise any UNKNOWN lift makes it UNKNOWN. Missing information is never promoted to
"working".

## 3. Pair classification (in this order)

1. No route → **OUT_OF_SCOPE** (`NO_MODELED_ROUTE`): the source data does not describe a lift connection.
2. An endpoint asserted INACCESSIBLE by the source → **CONFIRMED_BLOCKED** (`ENDPOINT_NOT_STEP_FREE`).
3. Some route AVAILABLE and both endpoints ACCESSIBLE/N.A. → **CONFIRMED_ACCESSIBLE**.
   Some route AVAILABLE but an endpoint UNKNOWN → **UNVERIFIED** (`ENDPOINT_ASSERTION_UNKNOWN`).
4. Else some route UNKNOWN → **UNVERIFIED** (`LIFT_STATUS_UNKNOWN`).
5. Else (every route needs an unavailable lift) → **CONFIRMED_BLOCKED** (`ALL_MODELED_ROUTES_BLOCKED`).

"Blocked" in case 5 means *no step-free route in the modeled lift network*. Ramps or level access that
the publisher does not describe could exist; the UI and the evidence panel say so.

## 4. Scenarios

A `Scenario` node stores overrides as `(:Scenario)-[:OVERRIDES {state}]->(:Lift)` on top of one named
status snapshot (`base_snapshot_id`). The effective state is *baseline observation, then overrides*.
Observations are never modified; deleting the override restores the baseline result exactly (tested).
A scenario built on another snapshot is rejected rather than silently mixed.

## 5. Impact and ranking

`Gain(i) = |CONFIRMED(S + i→AVAILABLE)| − |CONFIRMED(S)|` over the same pair set and snapshot.
Candidates are lifts that are UNAVAILABLE or UNKNOWN in the scenario and lie on at least one route.
Ranking key: gain ↓, UNVERIFIED pairs resolved ↓, pairs depending on the lift ↓, lift id ↑ — fully
deterministic and order-invariant (tested with shuffled inputs).

No cost, duration, passenger or social weight is used: none is available from a verifiable source.

**Repairs in series.** When two unavailable lifts sit on the same route, each scores 0 alone. The ranking
says so ("only pays off when repaired together") and the budget planner (`/plan?budget=k`) finds the exact
best set of *k* repairs: routes never leave a station, so gains are additive across stations; subsets are
enumerated per station (≤ 12 candidates) and combined with a knapsack. The greedy plan is returned next
to it for comparison (tests include a case where greedy is worse).

## 6. Freshness policy

Freshness is reported, never folded into the classification: the analysis is always "as of the snapshot
observation time". The publisher refreshes hourly, so age ≤ 2 h is CURRENT, ≤ 24 h AGING, older STALE,
and the header shows the age. This keeps replayed scenarios reproducible while making staleness visible.

## 7. Reproducibility

`AnalysisResult.id = "ana-" + sha256(snapshot id, sorted overrides, algorithm version, hash of the
route structure)[:16]`. The same inputs always give the same id and the same counts (tested).

## 8. Region layer (v0.3.0)

**Unit.** An ordered pair of stations (A, B), A ≠ B, both with at least one *boardable* platform: GTFS
`wheelchair_boarding = 1`, or an IDFM *Accessibilité en gare* level other than "not accessible" (the IDFM level wins
when present).

**Boarding points.** A platform × line. GTFS publishes one platform node per mode for RER/Transilien stations;
splitting it per line keeps an RER A outage from closing RER D.

**Journey.** A sequence of legs; a leg boards at a usable point and alights at a usable point of the same GTFS
pattern (riding through other stations needs nothing from them); between legs the traveller changes inside a
station from one usable point to another. Same-platform changes between patterns are not assumed.

**Point states per view.**
* *published*: all OPEN.
* *feed*: each PRIM outage makes the points it AFFECTS DOUBT. For Gares & Connexions outages matched to an SNCF lift
  (`MATCHES_LIFT`) at a station UNLOCK models, the station topology decides instead: with those lifts UNAVAILABLE and
  all others AVAILABLE, compare the platforms with ≥ 1 CONFIRMED_ACCESSIBLE exit route to the all-AVAILABLE case:
  none lost → OPEN, all lost → CLOSED, some → DOUBT (applied to every rail point of the station).
* *best*: RATP / unknown-operator outages as in *feed*; SNCF lifts from SNCF's hourly status on the station topology
  (UNKNOWN status cannot confirm, so it can yield DOUBT).

**Counts.** *Confirmed* = pairs reachable using OPEN points only; *possible* = OPEN or DOUBT. Exact: Tarjan SCC
condensation of the point/station-hub graph, then station bitsets propagated in reverse topological order.

**Ranking.** Each candidate (a non-SNCF PRIM outage removed, or an SNCF lift set AVAILABLE) is evaluated alone
against the *best* view; gain = additional confirmed pairs. Feed corrections: each G&C message contradicted by SNCF
(GHOST, or unresolved at a station where every SNCF lift works) removed from the *feed* view.

**Journey search.** Dijkstra, cost = stops ridden + 8 per boarding; the first of confirmed / possible / published
that has a route gives the verdict. Every leg is re-matched in Cypher before it is shown.

**Reconciliation verdicts.** GHOST, CONFIRMED, UNCLEAR (SNCF UNKNOWN), UNRESOLVED_STATION_ALL_WORKING, UNRESOLVED,
MISSING_FROM_FEED (SNCF UNAVAILABLE, not matched by any message).
