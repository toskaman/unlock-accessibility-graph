"""Second region: the same method on another network, with national open data only.

Île-de-France is UNLOCK's reference region (IDFM GTFS + IDFM lift status + PRIM). This module rebuilds the
two layers for another French region from sources that exist for the whole country:

* station layer  — SNCF Gares & Connexions NeTEx (stations, quays, lifts) + SNCF hourly lift status,
                   restricted to the region's départements (same code as Île-de-France);
* network layer  — SNCF national GTFS (TER, Intercités, TGV), restricted to the stations matched to the
                   region's SNCF stations;
* boardability   — the station's WheelchairAccess as declared by SNCF G&C NeTEx (the national GTFS carries
                   no wheelchair_boarding);
* usage weight   — SNCF « Fréquentation en gares » 2025 (passengers a year / 365).

Output: data/normalized/regions/<code>/{graph_input,network}.json and database/regions/<code>.rl.
"""
from __future__ import annotations

import functools
import json
from collections import defaultdict
from pathlib import Path

from .config import MANIFEST_PATH, NORMALIZED_DIR, RAW_DIR, ROOT

_SNCF = "SNCF trains (TER, Intercités, TGV)"
REGIONS: dict[str, dict] = {
    # mainland regions (2016 map); Corsica has no SNCF Gares & Connexions station
    "ara": {"name": "Auvergne-Rhône-Alpes", "network_label": _SNCF, "center": [4.9, 45.6], "zoom": 7.2,
            "departements": ("01", "03", "07", "15", "26", "38", "42", "43", "63", "69", "73", "74")},
    "bfc": {"name": "Bourgogne-Franche-Comté", "network_label": _SNCF, "center": [5.0, 47.2], "zoom": 7.3,
            "departements": ("21", "25", "39", "58", "70", "71", "89", "90")},
    "bre": {"name": "Bretagne", "network_label": _SNCF, "center": [-2.9, 48.1], "zoom": 7.6,
            "departements": ("22", "29", "35", "56")},
    "cvl": {"name": "Centre-Val de Loire", "network_label": _SNCF, "center": [1.7, 47.5], "zoom": 7.4,
            "departements": ("18", "28", "36", "37", "41", "45")},
    "ges": {"name": "Grand Est", "network_label": _SNCF, "center": [5.6, 48.7], "zoom": 7.2,
            "departements": ("08", "10", "51", "52", "54", "55", "57", "67", "68", "88")},
    "hdf": {"name": "Hauts-de-France", "network_label": _SNCF, "center": [2.8, 50.0], "zoom": 7.6,
            "departements": ("02", "59", "60", "62", "80")},
    "nor": {"name": "Normandie", "network_label": _SNCF, "center": [0.2, 49.2], "zoom": 7.6,
            "departements": ("14", "27", "50", "61", "76")},
    "naq": {"name": "Nouvelle-Aquitaine", "network_label": _SNCF, "center": [0.2, 45.4], "zoom": 6.8,
            "departements": ("16", "17", "19", "23", "24", "33", "40", "47", "64", "79", "86", "87")},
    "occ": {"name": "Occitanie", "network_label": _SNCF, "center": [2.2, 43.7], "zoom": 7.0,
            "departements": ("09", "11", "12", "30", "31", "32", "34", "46", "48", "65", "66", "81", "82")},
    "pdl": {"name": "Pays de la Loire", "network_label": _SNCF, "center": [-0.8, 47.4], "zoom": 7.5,
            "departements": ("44", "49", "53", "72", "85")},
    "pac": {"name": "Provence-Alpes-Côte d'Azur", "network_label": _SNCF, "center": [5.9, 43.9], "zoom": 7.4,
            "departements": ("04", "05", "06", "13", "83", "84")},
}
DATASETS = ("sncf_netex_accessibility", "sncf_lift_status", "sncf_gtfs", "sncf_frequentation")
GTFS = RAW_DIR / "sncf_national" / "sncf-gtfs.zip"
RIDERSHIP = RAW_DIR / "sncf_national" / "frequentation-gares.json"


def paths(code: str) -> dict[str, Path]:
    return {"normalized": NORMALIZED_DIR / "regions" / code, "store": ROOT / "database" / "regions" / f"{code}.rl"}


def _clean_id(s: str) -> str:
    """National GTFS stop point ids contain spaces ("StopPoint:OCETrain TER-87…"): keep ids URL- and key-safe."""
    return s.replace(" ", "_")


@functools.lru_cache(maxsize=1)
def _national_network(path: str, _mtime: float) -> str:
    from .network.gtfs_net import build_network
    return json.dumps(build_network(Path(path)))     # cached as text: every region gets its own copy


def build_network_region(gtfs_zip: Path, graph_input: dict, ridership: Path | None) -> dict:
    net = json.loads(_national_network(str(gtfs_zip), Path(gtfs_zip).stat().st_mtime))
    stations_sncf = {s["id"]: s for s in graph_input["stations"]}
    zone_to_sncf: dict[str, list[dict]] = defaultdict(list)
    for sz in graph_input["station_zone"]:
        zone_to_sncf[sz["zone_id"]].append(stations_sncf[sz["station_id"]])
    keep = {s["id"] for s in net["stations"] if s["id"] in zone_to_sncf}
    stations = [s for s in net["stations"] if s["id"] in keep]
    fr = {}
    if ridership and ridership.exists():
        for r in json.loads(ridership.read_text(encoding="utf-8")):
            v = r.get("total_voyageurs_2025")
            if r.get("code_uic_complet") and v:
                fr[str(r["code_uic_complet"]).lstrip("0")[-8:]] = v
    for s in stations:
        uic = s["id"].removeprefix("OCE")
        if uic in fr:
            s["entries_per_day"] = round(fr[uic] / 365)
            s["entries_days"] = 365
            s["entries_dataset"] = "sncf_frequentation"
    plat_ok = {}
    platforms = []
    for p in net["platforms"]:
        if p["station_id"] not in keep:
            continue
        acc = [x["wheelchair"] for x in zone_to_sncf[p["station_id"]]]
        p["wheelchair"] = "ACCESSIBLE" if "ACCESSIBLE" in acc else ("NOT_ACCESSIBLE" if acc else "UNKNOWN")
        p["access_source"] = "SNCF_NETEX_STATION_WHEELCHAIR_ACCESS"
        p["boardable"] = p["wheelchair"] == "ACCESSIBLE"
        plat_ok[p["id"]] = _clean_id(p["id"])
        p["id"] = plat_ok[p["id"]]
        platforms.append(p)
    patterns = []
    for t in net["patterns"]:
        stops = [plat_ok[x] for x in t["stops"] if x in plat_ok]
        if len(stops) < 2:
            continue
        term = next((p["station_id"] for p in platforms if p["id"] == stops[-1]), None)
        patterns.append({**t, "stops": stops, "terminus_station": term})
    used = {t["line_id"] for t in patterns}
    lines = [l for l in net["lines"] if l["id"] in used]
    return {"format": "unlock-network/1", "stations": stations, "platforms": platforms, "lines": lines,
            "patterns": patterns,
            "counts": {"stations": len(stations), "platforms": len(platforms), "lines": len(lines),
                       "patterns": len(patterns), "boardable_platforms": sum(p["boardable"] for p in platforms),
                       "stations_with_entries": sum("entries_per_day" in s for s in stations)},
            "note": "Stopping patterns are cut to the region's matched stations; hop counts are stops ridden "
                    "among them."}


def build(code: str, import_store: bool = True) -> dict:
    from .ingest.normalize import build as build_station_layer
    cfg = REGIONS[code]
    p = paths(code)
    out = p["normalized"]
    rep = build_station_layer(out_dir=out, departements=cfg["departements"], gtfs_zip=GTFS, zdc_csv=None,
                              dataset_keys=DATASETS, gtfs_key="sncf_gtfs")
    gi = json.loads((out / "graph_input.json").read_text(encoding="utf-8"))
    net = build_network_region(GTFS, gi, RIDERSHIP)
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    net["datasets"] = [manifest[k] for k in ("sncf_gtfs", "sncf_frequentation") if k in manifest]
    net["region"] = {"code": code, **cfg}
    (out / "network.json").write_text(json.dumps(net, ensure_ascii=False, separators=(",", ":")),
                                      encoding="utf-8", newline="\n")
    q = rep["counts"]
    res = {"quality": {
        "stations": q.get("netex_stop_places_in_region"),
        "stations_matched_to_gtfs": q.get("stations_matched_to_zone"),
        "lifts": q.get("lifts"),
        "lifts_with_status": q.get("lifts_with_status_record"),
        "lifts_two_resolved_ends": q.get("lifts_two_resolved_ends"),
        "declared_accessible_stations": sum(1 for s in gi["stations"] if s["wheelchair"] == "ACCESSIBLE"),
        "declared_accessible_in_network": len({p["station_id"] for p in net["platforms"] if p["boardable"]})},
        "station_layer": {k: rep["counts"].get(k) for k in (
        "netex_stop_places_in_region", "lifts", "lifts_with_status_record", "stations_matched_to_zone",
        "stations_unmatched_to_zone", "lifts_two_resolved_ends")}, "network": net["counts"]}
    if import_store:
        from .db import GraphStore
        from .ingest.load import import_all
        p["store"].parent.mkdir(parents=True, exist_ok=True)
        if p["store"].exists():
            import shutil
            shutil.rmtree(p["store"]) if p["store"].is_dir() else p["store"].unlink()
        with GraphStore(p["store"]) as db:
            res["store"] = import_all(db, out).get("after")
    return res


def compare_row(ns, code: str) -> dict:
    """One row of the France-wide comparison, from a loaded NetworkService (same numbers as its overview)."""
    ov = ns.overview()
    b, p = ov["views"]["best"], ov["views"]["published"]
    acc = set(ns.net.station_platforms)
    lifts_at = {l.station_id for l in ns.ss.lifts.values()}
    acc_with_lifts = [s for s in acc if any(x in lifts_at for x in ns.sncf_of.get(s, []))]
    return {
        "code": code, "name": ns.region["name"], "network": ns.region["network_label"],
        "stations": len(ns.stations), "accessible_stations": len(acc),
        "published": p["confirmed"], "confirmed": b["confirmed"], "possible": b["possible"],
        "share_confirmed": round(b["confirmed"] / p["confirmed"], 4) if p["confirmed"] else None,
        "stations_affected": b["stations_affected"],
        "sncf_lifts": len(ns.ss.lifts),
        "sncf_lifts_out": sum(1 for s in ns.ss.baseline_state.values() if s.value == "UNAVAILABLE"),
        "sncf_lifts_unknown": sum(1 for s in ns.ss.baseline_state.values() if s.value == "UNKNOWN"),
        "ratp_lifts_out": (ov.get("idfm_status") or {}).get("ratp_unavailable"),
        "accessible_stations_with_lifts": len(acc_with_lifts),
        "with_platform_exit_topology": sum(1 for s in acc_with_lifts if ns._p_all.get(s)),
        "sncf_status_observed_at": (ns.ss.snapshot or {}).get("observed_at"),
        "method": "IDFM GTFS + IDFM lift status + SNCF" if ov.get("idfm_status") else "national SNCF data only",
    }
