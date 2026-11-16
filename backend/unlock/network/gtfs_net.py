"""Île-de-France rail network (RER, Transilien, TER, metro, tram, funicular, cable car) from IDFM GTFS.

Produces the *network layer* of UNLOCK: which platforms exist at which station, whether
the publisher declares each one wheelchair-boardable (GTFS ``wheelchair_boarding``), and
the stopping patterns that connect them. Every fact here comes straight from the GTFS
file; nothing is inferred except de-duplicating identical stopping patterns.

Granularity is whatever GTFS publishes:
* metro / tram: one platform (quay) per direction or island;
* RER / Transilien / TER: one "monomodal stop place" per mode and station (GTFS does not
  split rail stations into tracks — UNLOCK's station layer does that from SNCF NeTEx).
"""
from __future__ import annotations

import csv
import io
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

RAIL_ROUTE_TYPES = {"0": "TRAM", "1": "METRO", "2": "RAIL", "6": "CABLE", "7": "FUNICULAR"}


def _rows(z: zipfile.ZipFile, name: str):
    with z.open(name) as f:
        yield from csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))


def build_network(gtfs_zip: Path) -> dict:
    z = zipfile.ZipFile(gtfs_zip)
    routes = {r["route_id"]: r for r in _rows(z, "routes.txt") if r["route_type"] in RAIL_ROUTE_TYPES}
    agencies = {a["agency_id"]: a["agency_name"] for a in _rows(z, "agency.txt")}
    trips = {t["trip_id"]: t for t in _rows(z, "trips.txt") if t["route_id"] in routes}

    seq: dict[str, list[tuple[int, str]]] = defaultdict(list)
    with z.open("stop_times.txt") as f:
        r = csv.reader(io.TextIOWrapper(f, encoding="utf-8-sig"))
        h = next(r)
        ti, si, qi = h.index("trip_id"), h.index("stop_id"), h.index("stop_sequence")
        for row in r:
            if row[ti] in trips:
                seq[row[ti]].append((int(row[qi]), row[si]))

    patterns: Counter = Counter()
    headsigns: dict[tuple, Counter] = defaultdict(Counter)
    for tid, s in seq.items():
        s.sort()
        t = trips[tid]
        key = (t["route_id"], t["direction_id"] or "0", tuple(x[1] for x in s))
        patterns[key] += 1
        headsigns[key][t["trip_headsign"] or ""] += 1

    used = {x for k in patterns for x in k[2]}
    stops = {}
    for s in _rows(z, "stops.txt"):
        stops[s["stop_id"]] = s
    stations: dict[str, dict] = {}
    platforms: dict[str, dict] = {}
    for pid in sorted(used):
        s = stops[pid]
        parent = s["parent_station"] or pid
        ps = stops.get(parent, s)
        zone_id = parent.split(":")[-1]
        stations.setdefault(zone_id, {"id": zone_id, "gtfs_id": parent, "name": ps["stop_name"],
                                      "lat": round(float(ps["stop_lat"] or s["stop_lat"]), 6),
                                      "lon": round(float(ps["stop_lon"] or s["stop_lon"]), 6)})
        platforms[pid] = {"id": pid, "station_id": zone_id, "name": s["stop_name"],
                          "wheelchair": {"1": "ACCESSIBLE", "2": "NOT_ACCESSIBLE"}.get(s["wheelchair_boarding"], "UNKNOWN"),
                          "lat": round(float(s["stop_lat"]), 6), "lon": round(float(s["stop_lon"]), 6),
                          "modes": set(), "lines": set()}
    lines = {}
    for rid, r in routes.items():
        lines[rid] = {"id": rid, "short_name": r["route_short_name"], "long_name": r["route_long_name"],
                      "mode": RAIL_ROUTE_TYPES[r["route_type"]], "color": r["route_color"],
                      "text_color": r["route_text_color"], "operator": agencies.get(r["agency_id"], "")}
    out_patterns = []
    for i, ((rid, d, s), n) in enumerate(sorted(patterns.items(), key=lambda kv: (kv[0][0], kv[0][1], -kv[1], kv[0][2]))):
        for pid in s:
            platforms[pid]["modes"].add(lines[rid]["mode"])
            platforms[pid]["lines"].add(rid)
        out_patterns.append({"id": f"{rid}:{d}:{i}", "line_id": rid, "direction": d, "trips": n,
                             "headsign": headsigns[(rid, d, s)].most_common(1)[0][0],
                             "terminus_station": platforms[s[-1]]["station_id"], "stops": list(s)})
    for p in platforms.values():
        p["modes"] = sorted(p["modes"])
        p["lines"] = sorted(p["lines"])
    used_lines = {p["line_id"] for p in out_patterns}
    return {
        "format": "unlock-network/1",
        "stations": sorted(stations.values(), key=lambda s: s["id"]),
        "platforms": sorted(platforms.values(), key=lambda p: p["id"]),
        "lines": sorted((l for l in lines.values() if l["id"] in used_lines), key=lambda l: (l["mode"], l["short_name"])),
        "patterns": out_patterns,
    }
