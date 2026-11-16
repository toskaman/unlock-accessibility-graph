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
Before public release, the entrant should re-confirm the Licence Mobilités terms for the derived GTFS facts.
