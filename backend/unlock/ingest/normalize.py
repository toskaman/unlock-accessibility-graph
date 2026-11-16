"""Normalise raw source snapshots into one deterministic graph-input document.

Output: data/normalized/graph_input.json (+ quality_report.json)

The document contains only (a) facts copied from a source record and
(b) derived facts that carry an explicit ``derivation`` label. It is the sole
input of the Relate importer, which keeps the import reproducible: the same raw
files always produce the same document (stable ordering, no wall-clock values
other than the snapshot's own recorded times).
"""
from __future__ import annotations

import csv
import io
import json
import math
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from ..config import IDF_DEPARTEMENTS, MANIFEST_PATH, NORMALIZED_DIR, RAW_DIR
from . import netex, spaces

STATUS_MAP = {"OK": "AVAILABLE", "KO": "UNAVAILABLE", "INCONNU": "UNKNOWN"}
ROUTE_TYPES = {"0": "TRAM", "1": "METRO", "2": "RAIL", "3": "BUS", "7": "FUNICULAR", "5": "CABLE"}


def _haversine(lat1, lon1, lat2, lon2) -> float:
    r = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _name_tokens(name: str) -> set[str]:
    n = spaces.normalize(name)
    n = re.sub(r"[^a-z0-9 ]+", " ", n)
    stop = {"gare", "de", "du", "des", "la", "le", "les", "d", "l", "sur", "et", "en", "rer", "sncf", "station"}
    return {t for t in n.split() if t not in stop and len(t) > 1}


def _name_score(a: str, b: str) -> float:
    ta, tb = _name_tokens(a), _name_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def load_status(path: Path) -> dict[str, dict]:
    rows = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            rows[r["id"]] = r
    return rows


def _gtfs_lines(zip_path: Path, wanted_areas: set[str]):
    """Return (area -> set(route_id), routes dict, area metadata, feed calendar span)."""
    with zipfile.ZipFile(zip_path) as z:
        def rd(name):
            return csv.DictReader(io.TextIOWrapper(z.open(name), encoding="utf-8-sig", newline=""))
        stops = list(rd("stops.txt"))
        areas = {s["stop_id"]: s for s in stops if s["location_type"] == "1"}
        child_to_area = {s["stop_id"]: s["parent_station"] for s in stops
                         if s["location_type"] == "0" and s["parent_station"] in wanted_areas}
        routes = {r["route_id"]: r for r in rd("routes.txt")}
        trip_route = {t["trip_id"]: t["route_id"] for t in rd("trips.txt")}
        area_routes: dict[str, set[str]] = defaultdict(set)
        with z.open("stop_times.txt") as raw:
            text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
            header = next(csv.reader([text.readline()]))
            ti, si = header.index("trip_id"), header.index("stop_id")
            for line in text:
                parts = line.split(",", max(ti, si) + 1)
                sid = parts[si]
                area = child_to_area.get(sid)
                if area:
                    rid = trip_route.get(parts[ti])
                    if rid:
                        area_routes[area].add(rid)
        cal = list(rd("calendar.txt"))
        span = (min(c["start_date"] for c in cal), max(c["end_date"] for c in cal)) if cal else (None, None)
    return area_routes, routes, areas, span


def build(raw_dir: Path = RAW_DIR, out_dir: Path = NORMALIZED_DIR, with_gtfs: bool = True) -> dict:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    published, places = netex.parse(raw_dir / "sncf" / "SNCF_GC_accessibilite_gares.xml")
    status = load_status(raw_dir / "sncf" / "etat-fonctionnement-elevatique-gare.csv")
    q: Counter = Counter()

    q["netex_stop_places_total"] = len(places)
    pilot = [p for p in places if p.insee[:2] in IDF_DEPARTEMENTS]
    q["netex_stop_places_idf"] = len(pilot)

    stations, quays, lifts, space_list, serves, snapshots = [], [], [], [], [], []
    unmatched_tokens = []
    status_snapshot_id = "sncf_lift_status@" + manifest["sncf_lift_status"]["sha256"][:12]
    observed_at = manifest["sncf_lift_status"].get("publisher_modified") or manifest["sncf_lift_status"]["retrieved_at"]

    for p in sorted(pilot, key=lambda x: x.id):
        a = p.assessment
        stations.append({
            "id": p.id, "uuid": p.uuid, "insee": p.insee, "name": p.name, "lon": p.lon, "lat": p.lat,
            "transport_mode": p.transport_mode, "stop_place_type": p.stop_place_type,
            "step_free": a.limits["StepFreeAccess"] if a else "UNKNOWN",
            "wheelchair": a.limits["WheelchairAccess"] if a else "UNKNOWN",
            "mobility_impaired_access": a.mobility_impaired_access if a else "UNKNOWN",
        })
        codes: dict[str, str] = {}
        for qu in sorted(p.quays, key=lambda x: x.id):
            qa = qu.assessment
            code = spaces.quay_code(qu.name)
            if code and code not in codes:
                codes[code] = qu.id
            q["quays"] += 1
            q[f"quay_step_free_{qa.limits['StepFreeAccess'] if qa else 'UNKNOWN'}"] += 1
            quays.append({
                "id": qu.id, "station_id": p.id, "name": qu.name, "public_code": qu.public_code,
                "code": code, "lon": qu.lon, "lat": qu.lat, "description": qu.description,
                "step_free": qa.limits["StepFreeAccess"] if qa else "UNKNOWN",
                "wheelchair": qa.limits["WheelchairAccess"] if qa else "UNKNOWN",
                "lift_free": qa.limits["LiftFreeAccess"] if qa else "UNKNOWN",
                "mobility_impaired_access": qa.mobility_impaired_access if qa else "UNKNOWN",
            })
        topo = spaces.derive(p.uuid, set(codes), [(l.id, l.name, l.description) for l in p.lifts])
        for sid, s in sorted(topo.spaces.items()):
            space_list.append({"id": s.id, "station_id": p.id, "name": s.name, "role": s.role,
                               "quay_id": codes.get(s.quay_code) if s.quay_code else None})
        for f in topo.serves:
            serves.append({"lift_id": f.lift_id, "space_id": f.space_id, "derivation": f.derivation,
                           "side_text": f.side_text, "side_index": f.side_index})
        unmatched_tokens += [{"station": p.name, "lift_id": lid, "token": t} for lid, t in topo.unmatched_tokens]
        for l in sorted(p.lifts, key=lambda x: x.id):
            q["lifts"] += 1
            st = status.get(l.id)
            lifts.append({
                "id": l.id, "station_id": p.id, "name": l.name, "description": l.description,
                "equipment_status_attr": l.status_attr, "depth_mm": l.depth_mm,
                "max_load_kg": l.max_load_kg, "width_mm": l.width_mm, "lon": l.lon, "lat": l.lat,
            })
            if st is None:
                q["lifts_without_status_record"] += 1
                continue
            q["lifts_with_status_record"] += 1
            if st.get("gareid") != p.uuid:
                q["status_gareid_mismatch"] += 1
            raw_state = (st.get("etat_de_fonctionnement") or "").strip().upper()
            state = STATUS_MAP.get(raw_state, "UNKNOWN")
            q[f"status_{state}"] += 1
            snapshots.append({
                "id": f"{status_snapshot_id}:{l.id}", "lift_id": l.id, "snapshot_id": status_snapshot_id,
                "state": state, "raw_state": raw_state, "observed_at": observed_at,
                "source_label": st.get("libelle"), "source_location": st.get("localisationdescriptive"),
            })

    # ---- space-graph quality
    role_counts = Counter(s["role"] for s in space_list)
    der_counts = Counter(f["derivation"] for f in serves)
    lifts_by_id = defaultdict(list)
    for f in serves:
        lifts_by_id[f["lift_id"]].append(f)
    q["lifts_two_resolved_ends"] = sum(1 for fs in lifts_by_id.values()
                                       if len({x["side_index"] for x in fs if x["derivation"] != "UNSPECIFIED_END"}) >= 2)
    q["lifts_one_resolved_end"] = sum(1 for fs in lifts_by_id.values()
                                      if len({x["side_index"] for x in fs if x["derivation"] != "UNSPECIFIED_END"}) == 1)
    q["lifts_no_resolved_end"] = q["lifts"] - q["lifts_two_resolved_ends"] - q["lifts_one_resolved_end"]

    # ---- IDFM anchoring (GTFS stop areas == IDFM ZdC ids)
    zones, station_zone, lines, zone_lines = [], [], [], []
    feed_span = (None, None)
    if with_gtfs:
        zdc = {}
        with open(raw_dir / "idfm" / "zones-de-correspondance.csv", encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f, delimiter=";"):
                zdc[r["zdcid"]] = r
        with zipfile.ZipFile(raw_dir / "gtfs" / "IDFM-gtfs.zip") as z:
            stops = list(csv.DictReader(io.TextIOWrapper(z.open("stops.txt"), encoding="utf-8-sig", newline="")))
        areas = [s for s in stops if s["location_type"] == "1"]
        q["gtfs_stop_areas"] = len(areas)
        q["gtfs_stop_areas_matching_zdc"] = sum(1 for s in areas if s["stop_id"].removeprefix("IDFM:") in zdc)
        matches = {}
        for st in stations:
            best = None
            for s in areas:
                d = _haversine(st["lat"], st["lon"], float(s["stop_lat"]), float(s["stop_lon"]))
                if d > 800:
                    continue
                ns = _name_score(st["name"], s["stop_name"])
                zid = s["stop_id"].removeprefix("IDFM:")
                ztype = zdc.get(zid, {}).get("zdctype", "")
                # accept: strong name agreement within 800 m, or rail zone within 250 m with some agreement
                ok = ns >= 0.5 or (ns > 0 and d <= 250 and ztype == "railStation")
                if not ok:
                    continue
                key = (-ns, d)
                if best is None or key < best[0]:
                    best = (key, s, d, ns, ztype)
            if best:
                _, s, d, ns, ztype = best
                matches[st["id"]] = s["stop_id"]
                station_zone.append({"station_id": st["id"], "zone_id": s["stop_id"].removeprefix("IDFM:"),
                                     "distance_m": round(d, 1), "name_score": round(ns, 3),
                                     "derivation": "NAME_AND_DISTANCE"})
        q["stations_matched_to_zone"] = len(matches)
        q["stations_unmatched_to_zone"] = len(stations) - len(matches)
        wanted = set(matches.values())
        area_routes, routes, gareas, feed_span = _gtfs_lines(raw_dir / "gtfs" / "IDFM-gtfs.zip", wanted)
        used_routes = set()
        for area_id in sorted(wanted):
            a = gareas[area_id]
            zid = area_id.removeprefix("IDFM:")
            z = zdc.get(zid, {})
            zones.append({"id": zid, "name": z.get("zdcname") or a["stop_name"], "type": z.get("zdctype"),
                          "town": z.get("zdctown"), "lon": float(a["stop_lon"]), "lat": float(a["stop_lat"]),
                          "in_zdc_reference": zid in zdc})
            rids = sorted(area_routes.get(area_id, ()))
            for rid in rids:
                r = routes[rid]
                mode = ROUTE_TYPES.get(r["route_type"], r["route_type"])
                if mode == "BUS":
                    continue
                used_routes.add(rid)
                zone_lines.append({"zone_id": zid, "line_id": rid})
        for rid in sorted(used_routes):
            r = routes[rid]
            lines.append({"id": rid, "short_name": r["route_short_name"], "long_name": r["route_long_name"],
                          "mode": ROUTE_TYPES.get(r["route_type"], r["route_type"]),
                          "color": r["route_color"] or None, "text_color": r["route_text_color"] or None})
        q["zones"] = len(zones)
        q["lines_non_bus"] = len(lines)
        q["zone_line_links"] = len(zone_lines)

    datasets = [dict(v, published=(published if k == "sncf_netex_accessibility" else None),
                     gtfs_calendar_span=list(feed_span) if k == "idfm_gtfs" else None)
                for k, v in sorted(manifest.items())]
    doc = {
        "format": "unlock-graph-input/1",
        "status_snapshot_id": status_snapshot_id,
        "status_observed_at": observed_at,
        "datasets": datasets, "stations": stations, "quays": quays, "lifts": lifts,
        "spaces": space_list, "serves": serves, "status_snapshots": snapshots,
        "zones": zones, "station_zone": station_zone, "lines": lines, "zone_lines": zone_lines,
    }
    report = {"counts": dict(sorted(q.items())), "space_roles": dict(role_counts),
              "serves_derivations": dict(der_counts), "unmatched_tokens": unmatched_tokens[:200],
              "unmatched_token_count": len(unmatched_tokens)}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "graph_input.json").write_text(json.dumps(doc, ensure_ascii=False, sort_keys=True, indent=1), encoding="utf-8", newline="\n")
    (out_dir / "quality_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    return report
