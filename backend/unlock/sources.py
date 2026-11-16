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
            role="IDFM transfer zones (ZdC) used to anchor SNCF stations in the regional stop reference",
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
