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

Investigated and **not used**:

| Dataset | Reason |
|---|---|
| IDFM `etat-des-ascenseurs` (Licence Mobilité) | Records require authentication (`ForbiddenAccess`); 986 records announced. Planned second source once a key is provided. |
| IDFM `acces`, `relations-acces`, `zones-d-arrets`, `relations` | Downloaded and inspected (hierarchy ZdC → ZdA → arrêt, accès → ZdA); not needed for the SNCF pilot. Will anchor RATP lifts (ZdC-level) later. |
| GTFS `pathways.txt` | 5,034 pathways, all walkways (mode 1), no levels → no lift topology. |
| Accèslibre (ERP accessibility) | Proximity to a station is not a verified accessible path; using it would overstate access. |
