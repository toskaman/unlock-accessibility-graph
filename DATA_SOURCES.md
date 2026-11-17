# Data sources

Declared in `backend/unlock/sources.py`; every download is recorded in `data/manifest/sources.json`
(url, bytes, sha256, retrieval time, publisher timestamp, licence). Untrusted inputs: downloads are
size-capped (400 MB), XML is parsed with the standard library (no external entities), CSV values are
treated as text and never evaluated.

| Key | Dataset | Publisher | Licence | Access | Snapshot used |
|---|---|---|---|---|---|
| `sncf_netex_accessibility` | Accessibilité des gares (NeTEx) | SNCF G&C | ODbL 1.0 | public FTP | published 2026-11-15T19:09:31Z, sha256 f66abe28… |
| `sncf_lift_status` | État de fonctionnement des équipements d'élévatique en gare | SNCF G&C | ODbL 1.0 | public API export, hourly | processed 2026-11-16T15:30:19Z, sha256 2273b7c1… |
| `idfm_zones_correspondance` | Référentiel des arrêts : Zones de correspondance | IDFM | Licence Ouverte 2.0 | public API export | modified 2026-11-16T01:00:47Z, sha256 36368ff1… |
| `idfm_gtfs` | Réseaux urbains et interurbains d'IDFM (GTFS) | IDFM | Licence Mobilités | public | calendar 2026-11-13 → 2026-12-15, sha256 6f450814… |

Added in v0.3.0:

| Key | Dataset | Publisher | Licence | Access | Notes |
|---|---|---|---|---|---|
| `idfm_accessibilite_en_gare` | Accessibilité en gare | IDFM | Licence Ouverte 2.0 | public | 459 rail stop points; levels 1/3/4/6 |
| `idfm_validations_ferre` | Validations sur le réseau ferré : nombre de validations par jour (T2 2026) | IDFM | Licence Ouverte 2.0 | public | aggregated by `id_zdc` at download (724 zones, 91 days) |
| `prim_lift_outages` | Calculateur IDFM – Messages Info Trafic (Navitia `line_reports`), tag « Ascenseur » | IDFM (PRIM) | Licence Mobilités | free PRIM token | 1,047 lift messages / 356 lifts on 16 Nov 2026; last lift update 9 Oct 2026 |

Added in v0.6.0:

| Key | Dataset | Publisher | Licence | Access | Notes |
|---|---|---|---|---|---|
| `idfm_etat_ascenseurs` | État des ascenseurs | IDFM (from RATP and SNCF agents' station rounds, published 3 times a day) | Licence Mobilités | free Opendatasoft API key (account on data.iledefrance-mobilites.fr) | 986 lifts (391 RATP, 595 SNCF; 566 SNCF ids equal to the NeTEx lift ids); each lift lists the levels it joins (« Ligne M4 direction X / Accès 2 »). Snapshot 17 Nov 2026 00:26 UTC (night: see METHODOLOGY §9) |
| `sncf_gtfs` | Horaires SNCF — GTFS théorique (TER, Intercités, TGV) | SNCF Voyageurs | ODbL 1.0 | public | second region; no `calendar.txt` (calendar_dates only), no `wheelchair_boarding`; stop point ids contain spaces (cleaned) |
| `sncf_frequentation` | Fréquentation en gares | SNCF G&C | ODbL 1.0 | public API export | passengers 2025 per station (UIC code), 2,998 stations |

Investigated and **not used**:

| Dataset | Reason |
|---|---|
| IDFM `acces`, `relations-acces`, `zones-d-arrets`, `relations` | Downloaded and inspected (hierarchy ZdC → ZdA → arrêt, accès → ZdA); not needed for the SNCF pilot. Will anchor RATP lifts (ZdC-level) later. |
| GTFS `pathways.txt` | 5,034 pathways, all walkways (mode 1), no levels → no lift topology. |
| Accèslibre (ERP accessibility) | Proximity to a station is not a verified accessible path; using it would overstate access. |
