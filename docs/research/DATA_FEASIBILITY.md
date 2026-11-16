# Data feasibility report

Snapshot date: **16 November 2026** (UTC retrieval 16:20). All numbers below are produced by
`python scripts/feasibility_metrics.py` → `docs/research/feasibility_metrics.json`, plus
`data/normalized/quality_report.json`. Every percentage shows its numerator and denominator.

## Verdict

**Feasible, with a re-scoped data foundation.** The brief assumed IDFM elevator status plus GTFS
pathways would give the topology. Two of those assumptions failed, so the gate forced a change:

1. **The IDFM elevator dataset (`etat-des-ascenseurs`) is not publicly readable.** The catalogue lists
   986 records under the *Licence Mobilité*, but the records API answers `ForbiddenAccess` and the CSV/JSON
   export returns an empty body without an API key. No key was fabricated; this source is deferred until the
   project owner supplies a PRIM key through `.env`.
2. **The IDFM GTFS contains no elevator topology.** `pathways.txt` has 5,034 pathways, **all
   `pathway_mode = 1` (walkway)**, from station entrances to stop areas; **0 elevator pathways (mode 5)**
   and **no `levels.txt`**. GTFS therefore cannot establish "this lift connects that platform".

What *does* support a real, inspectable lift-dependency graph is the pair of open datasets from
**SNCF Gares & Connexions** (ODbL): the NeTEx accessibility file (stations, quays, quay-level
accessibility assessments, lift equipment with location text) and the hourly lift status feed.
UNLOCK's pilot is therefore **every SNCF-managed station in Île-de-France** (401 stations, 588 lifts),
anchored to the IDFM stop reference (transfer zones) and to the lines serving each zone (IDFM GTFS).

## Investigation table

| Investigation | Result |
|---|---|
| GTFS access | Public, `https://eu.ftp.opendatasoft.com/stif/GTFS/IDFM-gtfs.zip`, 112,987,851 bytes, sha256 `6f450814…`. Licence Mobilités. |
| GTFS validity dates | `calendar.txt` span **2026-11-13 → 2026-12-15**. |
| GTFS files available | agency, attributions, booking_rules, calendar, calendar_dates, object_codes_extension, pathways, routes, shapes, stop_times, stops, ticketing_deep_links, transfers, trips. **No `levels.txt`.** |
| Reference-zone dataset | `zones-de-correspondance`: 15,574 ZdC, Licence Ouverte 2.0. GTFS stop areas (location_type 1): **15,406 / 15,406 (100 %)** have an id equal to a ZdC id. |
| Elevator access (IDFM) | **Blocked** — `ForbiddenAccess` without key (986 records announced). Deferred. |
| Elevator access (SNCF) | Public. Status feed: 2,547 rows, values OK 2,298 / KO 141 / INCONNU 108, refreshed hourly by the publisher. |
| Elevator identifiers | SNCF `id` (UUID). NeTEx `LiftEquipment/@id` uses the same UUID. 1,645 lifts, 1,645 unique. |
| Zone identifiers | NeTEx `StopPlace/@id` = `FR:<INSEE>:LMO:<uuid>:LOC`; status `gareid` = that uuid. |
| ID join success | Lift ↔ status: **1,645 / 1,645 (100 %)**. Status `gareid` ↔ StopPlace: **2,542 / 2,547 (99.8 %)**. 902 status rows are escalators/travelators (not lifts) and are ignored. |
| Duplicate identifiers | 0 in stations, quays, lifts, spaces, snapshots (asserted by `tests/data_quality`). |
| Missing identifiers / coordinates | 0 stop places without coordinates (2,800). |
| Verified platform relationships | Quay ↔ station: from NeTEx structure (exact). Quay step-free assessment: 2,062 ACCESSIBLE / 4,908 INACCESSIBLE nationally; IDF 842 / 438. `LiftFreeAccess` is `true` on **6,970 / 6,970** quays → **not informative**, not used. |
| Verified elevator-path relationships | No surveyed lift→platform topology exists in any open source. Derived from lift location text, every edge labelled: lifts with two resolved ends **338 / 588 (57.5 %)**, one resolved end **249 / 588 (42.3 %)**, none 1. SERVES edges: VOIE_TOKEN 479, QUAI_NUMBER 72, NAME_VOIE_TOKEN 3, NAMED_SPACE 564, UNSPECIFIED_END 251 (multi-stop lifts keep every listed level since 0.2.0). 60 track tokens did not match a quay and were *not* linked. |
| SNCF station → IDFM zone | **401 / 401 (100 %)** matched by name + distance (≤ 800 m); 7 matches have name score < 0.5; reviewed manually: 6 are the same place under another name (e.g. "Paris Est" → "Gare de l'Est", "Aéroport Charles de Gaulle 1" → "Aéroport CDG 1"), 1 is an adjacent but distinct station ("Massy TGV" → "Massy - Palaiseau", 230 m). Zone links are context only and never enter the impact metric. |
| Accèslibre access | Public API exists (`acceslibre.beta.gouv.fr/api/`), Licence Ouverte 2.0. **Not used**: no verified pedestrian path links an ERP to a station space; proximity alone would be a false accessibility claim. |
| License review | SNCF datasets ODbL 1.0 (attribution + share-alike on derived databases → `data/LICENSE-DATA.md`). IDFM reference data Licence Ouverte 2.0. IDFM GTFS Licence Mobilités (only derived zone→line facts are redistributed). Relate Apache-2.0. |
| Data timestamps | NeTEx `PublicationTimestamp` 2026-11-15T19:09:31Z. Status dataset `data_processed` 2026-11-16T15:30:19Z (used as observation time; the feed carries no per-record timestamp). |
| Geographic coverage | Île-de-France départements 75, 77, 78, 91, 92, 93, 94, 95 (INSEE prefix of the StopPlace id): 401 stations, 1,280 quays, 588 lifts, 392 IDFM zones, 51 rail/metro/tram lines. |
| Remaining uncertainty | Lift endpoints come from free text. Non-lift step-free links (ramps, level access) are absent from the source, so a "blocked" pair means *no modeled step-free route*. RATP metro/RER lifts need the IDFM key. |

## Calculated quality measures (pilot)

| Measure | Value |
|---|---|
| Source records (IDF) | 401 stations, 1,280 quays, 588 lifts, 588 status observations |
| Status states (IDF) | AVAILABLE 565, UNAVAILABLE 16, UNKNOWN 7 |
| Unknown accessibility values | 0 quays without an assessment in IDF (assessments are true/false only) |
| Modeled origin–destination pairs | 1,497 (platform↔platform, platform↔exit within a station) |
| Pairs with ≥ 1 modeled lift route | **705 / 1,497 (47.1 %)** |
| Baseline classification | CONFIRMED_ACCESSIBLE 582, CONFIRMED_BLOCKED 75, UNVERIFIED 48, OUT_OF_SCOPE 792 |
| Stale observations | Freshness is evaluated at view time (≤ 2 h CURRENT, ≤ 24 h AGING, else STALE). |

## Hard decision gate — outcome

* The precise lift → platform relationship is **not** in any open source as structured data. UNLOCK
  therefore never asserts it as surveyed fact: it derives it from the publisher's own location text,
  labels each edge with its derivation, and refuses to link unmatched tokens.
* Impact is computed only over pairs that have at least one modeled route; the rest are reported as
  OUT_OF_SCOPE, not as inaccessible.
* The central intervention-prioritisation concept is preserved, and works on the **real current
  status**: 16 lifts are out of service in IDF today, and the engine ranks their repairs.

## Pilot geography and spotlight station

The pilot is bounded by data, not by recognisability: all SNCF stations in IDF. Within it, the
stations with the most modeled routes are Paris Gare du Nord (85 pairs with routes), Juvisy-sur-Orge (66),
Paris Montparnasse (51), Versailles Chantiers (36) and Pontoise (29). **Juvisy-sur-Orge** (RER C & D,
12 platforms joined by an underpass) is the demo spotlight: it has the largest single-lift dependency in
the region (21 confirmed pairs depend on each of five lifts) and a readable cross-section.
