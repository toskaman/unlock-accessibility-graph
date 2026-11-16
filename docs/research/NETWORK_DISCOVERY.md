# From one station to the whole region — discovery, decision, evidence (v0.3.0)

*16 November 2026. Profile: HACKATHON (TITAN OMEGA v3.0 + v5.0), applied to an existing project.*

## Mission contract

| | |
|---|---|
| **Outcome** | A planner, an accessibility officer or a wheelchair user can see, for the **whole Île-de-France rail, metro and tram network**, which step-free journeys exist right now, which lift outages cut them, and which repair (or which data correction) gives the most back. |
| **Users** | Maintenance and accessibility teams at the operators and at IDFM; journey-planning re-users; riders who need lifts. |
| **Acceptance** | Region numbers come from an exact computation on the graph stored in Relate; every journey leg is re-checked in Relate; each outage placement carries a derivation; what is unknown is shown as unknown; numbers on screen are API numbers; tests and e2e green on Linux and Windows. |
| **Constraints** | Deadline 11 Dec 2026 18:00 PST. The PRIM token never leaves the entrant's machine (file on D:, env var) and is never committed. Licence Mobilités / ODbL / Licence Ouverte respected. No video (entrant records it). |
| **Non-goals** | Real-time push, a rider app, timetables, inventing redundancy information the sources do not publish. |
| **Stop condition** | The three views, ranking, journey check and reconciliation work end to end; an independent check of the outage → platform / lift matching is recorded; docs updated; release published. |

## What the PRIM token made possible

The token opens the PRIM *Calculateur IDFM — Messages Info Trafic* API (Navitia `line_reports`). It carries
lift outages for **both RATP and SNCF** stations, tagged `Ascenseur`, with free-text locations. It does
**not** open the restricted Opendatasoft dataset `etat-des-ascenseurs` (that needs a separate key from the
data.iledefrance-mobilites.fr account page; tested: 401/403).

Observed on 16 Nov 2026 at 19:13 UTC (13 pages, 1,355 line reports), again at **22:33 UTC** and at **23:14 UTC** from the entrant's Windows
machine with `python -m unlock fetch-outages` — the SHA-256 of all lift messages is identical at every
observation (`data/normalized/outage_feed_history.json`, `(:FeedObservation)` nodes); the committed snapshot is the
latest one:

| Fact | Value | Class |
|---|---|---|
| Active disruptions tagged `Ascenseur` | 1,047 messages | OBSERVED |
| Distinct lifts behind them (grouped by operator equipment id in `reference`) | 356 (264 SNCF Gares & Connexions, 89 RATP, 3 unknown) | OBSERVED |
| Most recent `updated_at` of any lift message | **2026-10-09 09:53** | OBSERVED |
| Most recent `updated_at` of non-lift messages in the same response | 2026-11-16 20:13 (same day) | OBSERVED |
| Lift messages older than 90 days / oldest | 180 / 363 days | OBSERVED |
| Messages whose own text announces an end date already past | 26 | OBSERVED |
| PRIM *Messages Info Trafic – requête globale* (`disruptions_bulk`) lift messages | 0 of 890 | OBSERVED |

**Interpretation (reasoned hypothesis, not confirmed by IDFM):** the lift messages of this API stopped being
updated on 9 October 2026 while the rest of the feed kept moving. We do not know whether the IDFM apps show
these messages; we only claim what the API returns to re-users.

## Cross-check against SNCF's own hourly feed

UNLOCK reads every Gares & Connexions message with its incident resolver, restricted to the SNCF stations
of the same IDFM transfer zone (graph path `NStation-[:IS_ZONE]->TransferZone<-[:IN_TRANSFER_ZONE]-Station`):

| Verdict | Lifts | Meaning |
|---|---|---|
| GHOST | 159 | Resolved to one SNCF lift that SNCF's hourly feed reports **working** |
| UNRESOLVED_STATION_ALL_WORKING | 76 | Not resolved to one lift, but **every** SNCF lift at that station is reported working |
| CONFIRMED | 9 | Resolved, and SNCF also reports it out of service |
| UNRESOLVED | 20 | Not resolved and the station has a lift SNCF does not report working |
| MISSING_FROM_FEED | 7 | Out of service in SNCF's feed, absent from PRIM |

So 235 of the 264 SNCF lifts listed out of service by PRIM are contradicted by the operator's own hourly
data. The independent check of the matching is in [`region_eval/`](region_eval/README.md): 29/30 resolver matches
judged correct, 1 plausible, 0 wrong.

## Candidate killer features (scored before building)

Scores /10: pain · improvement · demo · originality · technical · rubric fit · feasibility · reliability · evidence.

| Candidate | Scores | Total | Decision |
|---|---|---|---|
| **A. Region-wide journeys under real outages** (GTFS network in Relate + PRIM outages + station topology) | 9 9 9 8 9 10 7 8 8 | 77 | **Build** |
| **B. "Can I get there in a wheelchair?"** journey check A→B with legs and the outages on the way | 9 8 9 6 7 9 8 8 8 | 72 | **Build (on A)** |
| **C. Stale-feed reconciliation** PRIM vs SNCF, with journeys hidden by wrong messages | 8 9 10 9 7 9 8 8 9 | 77 | **Build (on A)** |
| D. Redundancy-aware RATP layer from `etat-des-ascenseurs` | 8 8 6 6 7 8 3 7 7 | 60 | Blocked: needs an ODS key the entrant must create |
| E. Region "chokepoints" (single platforms whose loss cuts most journeys) | 6 6 6 7 7 8 8 9 7 | 64 | Built, measured, **dropped**: only 3 points cut journeys between other stations — the published step-free network is redundant at single-platform level; impact comes from combinations of outages |
| F. Daily outage brief for maintenance teams | 6 6 4 3 4 6 9 9 6 | 53 | Not built |

## What was built

* **Network layer in Relate** — 996 `NStation`, 1,953 `NPlatform` (881 wheelchair-boardable), 59 `NLine`,
  1,055 `NPattern`, 14,077 `NEXT`, 14,147 `LEG` (rides between boardable platforms), `IS_ZONE` links to the
  SNCF station layer.
* **Outage feed in Relate** — immutable `OutageFeed` snapshot, 356 `LiftOutage`, 583 `AFFECTS` (derivation on
  each), 168 `MATCHES_LIFT` (resolver, same zone).
* **Engine** — exact reachability of all ordered station pairs (SCC condensation + bitsets, ~10 ms), three
  views (published / PRIM feed / best available), ranking of repairs and of feed corrections, least-cost
  journey search with every leg re-checked in Cypher.
* **UI** — *Whole region* mode (default): headline numbers per view, frozen-feed card, map coloured by
  state, journey check comparing the three views, station card with each message, its age and SNCF's
  verdict, link into the existing station cross-section.
* **MCP** — `check_journey`, `region_overview`, `region_repairs`, `station_outages` tools.

## Results (snapshot of 16 Nov 2026)

| | Published | Best available | PRIM feed |
|---|---|---|---|
| Confirmed step-free ordered station pairs | 256,592 | 192,377 | 88,255 |
| Possible if every listed lift works | 256,592 | 253,562 | 239,660 |

* Removing only the 235 PRIM messages that SNCF contradicts gives back **96,340** confirmed journeys in the
  feed view.
* Top repair (best view): an RATP lift at **La Croix de Berny** (RER B, listed since 9 Oct) — **+27,156**:
  with the Viroflay Rive Gauche lift also listed out (since 17 Nov 2025), the T6/T10 tram stations have no
  confirmed step-free connection to the rest of the network. RATP messages come only from the frozen feed:
  the UI says "check on site".

## Independent check and the fix it caused

A separate agent labelled 40 placements and 30 lift matches from the message text alone
([region_eval/](region_eval/README.md)). Round 1: lines 33 correct / 2 superset / **3 wrong** / 2 unclear; matches
29 correct / 1 plausible / 0 wrong. The 3 wrong cases came from trusting the feed's own line links; they were
dropped. After the fix (round 2 on the changed cases): 34 correct / 4 superset / 2 unclear / **0 wrong**.

## Limits (stated in the product)

* RATP lift status exists only in the frozen PRIM feed; "best available" still uses it.
* No redundancy information for RATP lifts: a listed outage removes *confirmation* (DOUBT), it does not
  block. Only SNCF stations, with UNLOCK's lift-by-lift topology, can be CLOSED.
* GTFS gives one platform node per mode for RER/Transilien stations; UNLOCK splits it per line, not per track.
* Journeys are ordered station pairs, not trips or people; transfers are assumed step-free between two
  boardable platforms of the same station (GTFS `parent_station`), which is what `wheelchair_boarding`
  promises for each platform separately.
