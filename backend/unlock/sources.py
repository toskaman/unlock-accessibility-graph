"""Registry of every external data source UNLOCK reads.

Each entry is the single place where a URL, licence and publisher are declared.
The fetch script records what it actually downloaded (bytes, sha256, time) in
``data/manifest/sources.json``; the importer copies that record into the graph
as a ``:Dataset`` node so every derived fact can be traced back to a file hash.
"""
from __future__ import annotations

from dataclasses import dataclass

IDFM_API = "https://data.iledefrance-mobilites.fr/api/explore/v2.1/catalog/datasets"
SNCF_API = "https://ressources.data.sncf.com/api/explore/v2.1/catalog/datasets"


@dataclass(frozen=True)
class Source:
    key: str
    title: str
    publisher: str
    url: str
    filename: str
    licence: str
    licence_url: str
    role: str
    metadata_url: str | None = None


SOURCES: dict[str, Source] = {
    s.key: s
    for s in [
        Source(
            key="sncf_netex_accessibility",
            title="Accessibilité des gares (NeTEx)",
            publisher="SNCF Gares & Connexions",
            url="https://eu.ftp.opendatasoft.com/sncf/G&C/NeTEx_accessibilite/SNCF_GC_accessibilite_gares.xml",
            filename="sncf/SNCF_GC_accessibilite_gares.xml",
            licence="ODbL 1.0",
            licence_url="https://data.sncf.com/pages/licence",
            role="Stations, platforms (quays), platform accessibility assessments, lift equipment and lift location text",
            metadata_url=f"{SNCF_API}/accessibilite_gares",
        ),
        Source(
            key="sncf_lift_status",
            title="Etat de fonctionnement des équipements d'élévatique en gare",
            publisher="SNCF Gares & Connexions",
            url=f"{SNCF_API}/etat-fonctionnement-elevatique-gare/exports/csv?delimiter=%3B&use_labels=false",
            filename="sncf/etat-fonctionnement-elevatique-gare.csv",
            licence="ODbL 1.0",
            licence_url="https://data.sncf.com/pages/licence",
            role="Latest published lift status (OK / KO / INCONNU), refreshed hourly by the publisher",
            metadata_url=f"{SNCF_API}/etat-fonctionnement-elevatique-gare",
        ),
        Source(
            key="idfm_zones_correspondance",
            title="Référentiel des arrêts : Zones de correspondance",
            publisher="Île-de-France Mobilités",
            url=f"{IDFM_API}/zones-de-correspondance/exports/csv?delimiter=%3B&use_labels=false",
            filename="idfm/zones-de-correspondance.csv",
            licence="Licence Ouverte v2.0 (Etalab)",
            licence_url="https://www.etalab.gouv.fr/licence-ouverte-open-licence/",
            role="IDFM transfer zones (ZdC) used to anchor SNCF stations in the regional stop reference; "
                 "zdcpostalregion locates Transilien/RER stops absent from the national GTFS",
            metadata_url=f"{IDFM_API}/zones-de-correspondance",
        ),
        Source(
            key="idfm_gtfs",
            title="Réseaux urbains et interurbains d'Île-de-France Mobilités (GTFS)",
            publisher="Île-de-France Mobilités",
            url="https://eu.ftp.opendatasoft.com/stif/GTFS/IDFM-gtfs.zip",
            filename="gtfs/IDFM-gtfs.zip",
            licence="Licence Mobilités",
            licence_url="https://transport.data.gouv.fr/datasets/reseaux-urbains-et-interurbains-dile-de-france-mobilites",
            role="Lines (routes) calling at each transfer zone, from stops/stop_times/trips/routes; "
                 "network layer: platforms, wheelchair_boarding and stopping patterns of rail/metro/tram lines",
        ),
        Source(
            key="idfm_accessibilite_en_gare",
            title="Accessibilité en gare",
            publisher="Île-de-France Mobilités",
            url=f"{IDFM_API}/accessibilite-en-gare/exports/json",
            filename="idfm/accessibilite-en-gare.json",
            licence="Licence Ouverte v2.0 (Etalab)",
            licence_url="https://www.etalab.gouv.fr/licence-ouverte-open-licence/",
            role="Rail stop accessibility level (autonomous, on request to an agent, booked AssistenGare, not accessible)",
            metadata_url=f"{IDFM_API}/accessibilite-en-gare",
        ),
        Source(
            key="sncf_gtfs",
            title="Horaires SNCF (GTFS théorique TER, Intercités, TGV)",
            publisher="SNCF Voyageurs",
            url="https://eu.ftp.opendatasoft.com/sncf/plandata/Export_OpenData_SNCF_GTFS_NewTripId.zip",
            filename="sncf_national/sncf-gtfs.zip",
            licence="Open Database License (ODbL)",
            licence_url="https://opendatacommons.org/licenses/odbl/1-0/",
            role="National train timetables: stations, stop points and stopping patterns for regions outside "
                 "Île-de-France (second-region network layer)",
            metadata_url=f"{SNCF_API}/horaires-sncf",
        ),
        Source(
            key="sncf_frequentation",
            title="Fréquentation en gares",
            publisher="SNCF Gares & Connexions",
            url=f"{SNCF_API}/frequentation-gares/exports/json",
            filename="sncf_national/frequentation-gares.json",
            licence="Open Database License (ODbL)",
            licence_url="https://opendatacommons.org/licenses/odbl/1-0/",
            role="Passengers per station per year (2025): a weight for how many people use a station, "
                 "not a count of wheelchair users; UIC + postcode locate NeTEx stop places in a département "
                 "since the 2026-11-24 NeTEx carries no INSEE code",
            metadata_url=f"{SNCF_API}/frequentation-gares",
        ),
        Source(
            key="idfm_validations_ferre",
            title="Validations sur le réseau ferré : Nombre de validations par jour (2ème trimestre 2026)",
            publisher="Île-de-France Mobilités",
            url=f"{IDFM_API}/validations-reseau-ferre-nombre-validations-par-jour-2eme-trimestre/exports/json"
                "?select=id_zdc,sum(nb_vald)%20as%20v,count(distinct%20jour)%20as%20d&group_by=id_zdc",
            filename="idfm/validations-ferre-q2-2026.json",
            licence="Licence Ouverte v2.0 (Etalab)",
            licence_url="https://www.etalab.gouv.fr/licence-ouverte-open-licence/",
            role="Average daily ticket validations per transfer zone (all riders), Apr–Jun 2026 — a weight for "
                 "how many people use a station, not a count of wheelchair users",
            metadata_url=f"{IDFM_API}/validations-reseau-ferre-nombre-validations-par-jour-2eme-trimestre",
        ),
    ]
}


# Needs a personal PRIM API token (free account). Fetched by `python -m unlock fetch-outages`, never by `fetch`.
PRIM_LINE_REPORTS = Source(
    key="prim_lift_outages",
    title="Calculateur Île-de-France Mobilités - Messages Info Trafic (Navitia line_reports), tag « Ascenseur »",
    publisher="Île-de-France Mobilités (PRIM)",
    url="https://prim.iledefrance-mobilites.fr/marketplace/v2/navitia/line_reports/line_reports",
    filename="prim/line_reports.json",
    licence="Licence Mobilités",
    licence_url="https://prim.iledefrance-mobilites.fr/fr/licences",
    role="Lift outages published to passengers and re-users for RATP and SNCF stations, with location text",
)
