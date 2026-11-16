# Data licences and attribution

The files `data/normalized/graph_input.json`, `data/normalized/quality_report.json` and the Relate store
`database/snapshot/unlock-snapshot-2026-11-16.rl` are a **derived database** produced by UNLOCK from:

| Source | Publisher | Licence |
|---|---|---|
| Accessibilité des gares (NeTEx), retrieved 2026-11-16 | SNCF Gares & Connexions | Open Database License (ODbL) 1.0 — https://data.sncf.com/pages/licence |
| État de fonctionnement des équipements d'élévatique en gare, retrieved 2026-11-16 | SNCF Gares & Connexions | ODbL 1.0 |
| Référentiel des arrêts : Zones de correspondance | Île-de-France Mobilités | Licence Ouverte v2.0 (Etalab) |
| Réseaux urbains et interurbains d'IDFM (GTFS) — only derived "line calls at zone" facts | Île-de-France Mobilités | Licence Mobilités |

Contains information from SNCF Gares & Connexions, made available under the ODbL.
Contains information from Île-de-France Mobilités (Licence Ouverte 2.0 / Licence Mobilités).

Because the SNCF inputs are ODbL, this derived database is made available under the **ODbL 1.0**
(share-alike). Fields derived by UNLOCK (spaces, SERVES edges, zone matches) carry a `derivation` label.
Raw source files are **not** redistributed; `python -m unlock fetch` downloads them from the publishers.
### Licence Mobilités (IDFM GTFS) — check done 2026-11-16

The Licence Mobilités (version 03.02.2021) grants a royalty-free, worldwide, non-exclusive right to extract,
re-use, create derived databases and distribute them, commercial use included (art. 3.1). Its obligations that
apply here: keep the licence notice/URI when publicly sharing a derived database (art. 5.3), state that the
content originates from the IDFM database (art. 5.4), share a publicly used derived database under the same or a
compatible licence (share-alike, art. 5.5), and offer it free of charge online (art. 5.8). Extracting a
non-substantial part is free (art. 8.2).

UNLOCK redistributes only 51 line records and 551 "line calls at transfer zone" links derived from the GTFS
(out of ~2,000 routes and ~15,400 stop areas), not the feed itself. They are published here, free of charge,
with this notice: *Contains information from Île-de-France Mobilités, "Réseaux urbains et interurbains d'IDFM"
(GTFS), licensed under the Licence Mobilités — https://transport.data.gouv.fr/datasets/reseaux-urbains-et-interurbains-dile-de-france-mobilites.*
These derived records remain under the Licence Mobilités; the rest of the derived database is under the ODbL.
This is a good-faith reading of the licence text, not legal advice.

## Added in v0.3.0

* **IDFM GTFS (Licence Mobilités)** — the region layer redistributes, in `data/normalized/network.json`, the
  rail/metro/tram stations, platforms (with `wheelchair_boarding`), lines and distinct stop sequences (1,055) — a
  small extract of the feed (no times, no buses). Same notice and licence as above.
* **IDFM *Accessibilité en gare* (Licence Ouverte 2.0)** — accessibility level per rail stop. *Source : Île-de-France
  Mobilités, « Accessibilité en gare », Licence Ouverte 2.0.*
* **PRIM *Messages Info Trafic* (Licence Mobilités)** — `data/normalized/network_outages.json` keeps, per lift, the
  message text, dates and placement for the 356 lifts listed on 16 Nov 2026. *Contains information from
  Île-de-France Mobilités (PRIM), « Calculateur Île-de-France Mobilités – Messages Info Trafic », licensed under the
  Licence Mobilités.* The raw API response (`data/raw/prim/`) is not committed and the access token never is.
