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

import json
from collections import defaultdict
from pathlib import Path

from .config import MANIFEST_PATH, NORMALIZED_DIR, RAW_DIR, ROOT

REGIONS: dict[str, dict] = {
    "ara": {
        "name": "Auvergne-Rhône-Alpes",
        "network_label": "SNCF trains (TER, Intercités, TGV)",
        "departements": ("01", "03", "07", "15", "26", "38", "42", "43", "63", "69", "73", "74"),
        "center": [4.9, 45.6], "zoom": 7.2,
    },
}
DATASETS = ("sncf_netex_accessibility", "sncf_lift_status", "sncf_gtfs", "sncf_frequentation")
GTFS = RAW_DIR / "sncf_national" / "sncf-gtfs.zip"
RIDERSHIP = RAW_DIR / "sncf_national" / "frequentation-gares.json"


def paths(code: str) -> dict[str, Path]:
    return {"normalized": NORMALIZED_DIR / "regions" / code, "store": ROOT / "database" / "regions" / f"{code}.rl"}


def _clean_id(s: str) -> str:
    """National GTFS stop point ids contain spaces ("StopPoint:OCETrain TER-87…"): keep ids URL- and key-safe."""
    return s.replace(" ", "_")


def build_network_region(gtfs_zip: Path, graph_input: dict, ridership: Path | None) -> dict:
    from .network.gtfs_net import build_network
    net = build_network(gtfs_zip)
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
    res = {"station_layer": {k: rep["counts"].get(k) for k in (
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
