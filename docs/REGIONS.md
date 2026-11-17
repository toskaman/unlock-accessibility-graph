# Every region of mainland France: does the method travel?

Île-de-France is where UNLOCK was built, with sources only Île-de-France has (IDFM GTFS with
`wheelchair_boarding`, IDFM lift status, PRIM). To check that the method is not an Île-de-France special case,
the same pipeline runs on **every region of mainland France** (11 besides Île-de-France; Corsica has no SNCF
G&C station) with sources published for the whole of France. The table below is for Auvergne-Rhône-Alpes; the
others are identical apart from their départements.

| Layer | Île-de-France | Auvergne-Rhône-Alpes |
|---|---|---|
| Stations, quays, lifts, lift location text | SNCF G&C NeTEx | same file (12 départements instead of 8) |
| Lift status | SNCF hourly feed + IDFM *État des ascenseurs* (RATP) | SNCF hourly feed |
| Network (stations, stop points, stopping patterns) | IDFM GTFS | SNCF national GTFS (TER, Intercités, TGV), ODbL |
| Which platforms a wheelchair user can board at | GTFS `wheelchair_boarding` + IDFM *Accessibilité en gare* | the station's `WheelchairAccess` in SNCF G&C NeTEx (the national GTFS has none) |
| Station ↔ network anchoring | IDFM transfer zone (ZdC) ids | name + distance to the GTFS stop area (same matcher) |
| Usage weight | IDFM validations Q2 2026 | SNCF *Fréquentation en gares* 2025 ÷ 365, ODbL |
| Outage messages | PRIM (frozen) | none — the *feed* view is not shown |

```bash
python -m unlock build-region all    # ~1 min for all 11: station layers + networks + database/regions/<code>.rl
python scripts/regions_report.py     # comparison + quality audit → data/normalized/regions/summary.json
python -m unlock serve               # the region picker appears; or ?region=ara on any /api/region/* call
python -m unlock bulletin --store database/regions/ara.rl
python -m unlock mcp --store database/regions/ara.rl
```

Code: `backend/unlock/regions.py` (≈130 lines) — everything else (station topology, Relate import, three views,
exact reachability, journeys verified in Cypher, repairs, rider alerts, bulletin, MCP) is the code Île-de-France
uses, unchanged. Adding a region is one entry in `REGIONS` (name, départements, map centre).

## Quality, region by region

`scripts/regions_report.py` reports, per region: stations matched to the timetable (93–100 %), lifts with a status
record (100 %), lifts whose two ends were read from the text, and — the number that matters most — **how many
declared-accessible stations with lifts have a modelled platform↔street route** (from 2 of 20 in Nouvelle-Aquitaine to
32 of 46 in Auvergne-Rhône-Alpes; 61 of 190 in Île-de-France). It also lists every weak station match (name score
< 0.75 or > 400 m). All 164 were read: 163 are the same station under a longer or shorter name (« Valence » ↔
« Valence Ville », « Belfort » ↔ « Belfort-Ville »), mostly within 0–120 m; one was wrong — « Mulhouse Zu Rhein
Tram-Train » matched to « Mulhouse Dornach Tram Train » 777 m away. Partial names more than 400 m away are now
rejected for the national timetable (Île-de-France matching unchanged).

Where no street route is modelled, a lift not reported working puts the station in doubt (D31). So a region's share
of *confirmed* journeys mixes real outages and missing topology: read it with the last column. A low share where most
stations are modelled (Occitanie: 8 of 14) points at outages; a low share where few are (Nouvelle-Aquitaine: 2 of 20)
points at the lift text first.

## What generalising found

- **Silent outages.** Before D31, a lift out of service at a station whose lift text names no exit changed nothing:
  Hauts-de-France read 100 % confirmed with 7 lifts out. Building every region exposed it; the fix also applies to
  Île-de-France (−6,328 confirmed journeys on the same status).

- **A parser bug that also affected Île-de-France.** Lift text like *"Hall et Voies A et S / Souterrain Nord"* is
  common in Auvergne-Rhône-Alpes. The track-list tokenizer treated the letter **A** as the word "à" (as in
  "voies 1 à 4") and dropped track A, and an exit named on the same side as a track (the hall) was lost. Fixed for
  both regions (`NAMED_SPACE_WITH_TRACK`, range word only between two numbers); Île-de-France gains the
  corresponding SERVES edges (see CHANGELOG 0.6.0).
- **Less is declared outside Île-de-France.** Only 51 of 330 SNCF stations in Auvergne-Rhône-Alpes are declared
  wheelchair-accessible in NeTEx, so the published step-free network is small (2,550 ordered station pairs). The
  method does not invent accessibility the publisher does not declare.
- **Stations without an exit space in the lift text** (e.g. the building at track level, never named) have no
  modelled platform↔street pair; their rail points stay "not modelled" (treated as open) rather than guessed.

## Licences

The national GTFS and *Fréquentation en gares* are ODbL: `data/normalized/regions/ara/*` is a derived database
published under ODbL with attribution to SNCF Voyageurs and SNCF Gares & Connexions (LICENSE-DATA.md).
