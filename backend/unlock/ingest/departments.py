"""Assign every SNCF stop place to a French département.

Until 2026-11-23 the NeTEx StopPlace id carried the station's INSEE commune
code (``FR:<INSEE>:LMO:<uuid>:LOC``). The file published 2026-11-24 changed the
layout to ``FR::monomodalStopPlace:<uuid>:LOC`` with no geography left — only
the name and the centroid. Region builds therefore recover the département
from other open sources, in order:

A. ``UIC_POSTAL`` — match the stop place to the national SNCF GTFS by name and
   distance, read the UIC out of the GTFS stop id (``StopArea:OCE<8 digits>``),
   and take the postcode of the Fréquentation row with that UIC. The postcode's
   département must belong to the row's ``direction_regionale_gares``; a row
   that fails this check (e.g. Pont-sur-Yonne filed under 14130 on 24 Nov
   2026) quarantines the station instead of misplacing it.
B. ``ZDC_POSTALREGION`` — match to the IDFM GTFS and read ``zdcpostalregion``
   (the INSEE commune code) of the transfer zone. Covers the Transilien/RER
   stops absent from the national GTFS.

A stop place that matches nothing is left unassigned and dropped from the
build, counted in the quality report: unknown is not a guess.

Measured 2026-11-24 on the 2,800 stop places of the new file against the
previous file's INSEE codes (joined by stable station uuid): 2,381 agree
through chain A, 384 through chain B, 31 unassigned (small TER halts absent
from both GTFS feeds), 1 quarantined (Pont-sur-Yonne), 1 corrected
(Fougeré: the old id said 49, every coordinate-bearing source says 85).
"""
from __future__ import annotations

import csv
import functools
import io
import json
import math
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from . import spaces

# direction_regionale_gares -> départements it may contain. Derived from the
# region map (backend/unlock/regions.py); a unit test fails loudly on drift.
# "98" (Monaco) is served by the SUD directorate but belongs to no region.
DRG_DEPARTMENTS: dict[str, frozenset[str]] = {
    "DEX GIF": frozenset({"75", "77", "78", "91", "92", "93", "94", "95"}),
    "ETAB GARES PARIS": frozenset({"75", "77", "78", "91", "92", "93", "94", "95"}),
    "DRG AURA BFC": frozenset({"01", "03", "07", "15", "26", "38", "42", "43", "63", "69", "73", "74",
                               "21", "25", "39", "58", "70", "71", "89", "90"}),
    "DRG B-CVL-PDL": frozenset({"22", "29", "35", "56",
                                "18", "28", "36", "37", "41", "45",
                                "44", "49", "53", "72", "85"}),
    "DRG GRAND EST": frozenset({"08", "10", "51", "52", "54", "55", "57", "67", "68", "88"}),
    "DRG HDF-NORMANDIE": frozenset({"02", "59", "60", "62", "80", "14", "27", "50", "61", "76"}),
    "DRG NLLE AQUITAINE": frozenset({"16", "17", "19", "23", "24", "33", "40", "47", "64", "79", "86", "87"}),
    "DRG OCCITANIE": frozenset({"09", "11", "12", "30", "31", "32", "34", "46", "48", "65", "66", "81", "82"}),
    "DRG SUD": frozenset({"04", "05", "06", "13", "83", "84", "98"}),
}


@dataclass(frozen=True)
class DeptAssignment:
    dept: str          # "" when quarantined
    derivation: str    # UIC_POSTAL | ZDC_POSTALREGION | QUARANTINED_DRG_MISMATCH
    evidence: str      # short deterministic human-readable trail


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
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


def name_score(a: str, b: str) -> float:
    ta, tb = _name_tokens(a), _name_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def dept_of_postal(code: str | None) -> str:
    """Postcode -> département, with the Corsican 2A/2B split."""
    cp = str(code or "").strip()
    if len(cp) < 2:
        return ""
    if cp[:2] == "20" and len(cp) >= 3:
        return "2A" if cp[:3] in ("200", "201") else "2B"
    return cp[:2]


def _uic_norm(code: str) -> str:
    return str(code or "").lstrip("0")[-8:]


def _gtfs_areas(zip_path: Path) -> list[tuple[str, str, float, float]]:
    """(stop_id, stop_name, lat, lon) of every stop area; [] when unreadable."""
    try:
        with zipfile.ZipFile(zip_path) as z:
            rows = list(csv.DictReader(io.TextIOWrapper(z.open("stops.txt"), encoding="utf-8-sig", newline="")))
    except OSError:
        return []
    out = []
    for s in rows:
        if s.get("location_type") != "1":
            continue
        try:
            out.append((s["stop_id"], s["stop_name"], float(s["stop_lat"]), float(s["stop_lon"])))
        except (KeyError, ValueError):
            continue
    return out


def _best_match(name: str, lat: float, lon: float, areas: list[tuple[str, str, float, float]],
                zdc: dict | None, national: bool):
    """Mirror of the station anchoring in normalize.py: best (stop_id, name, d, ns) or None."""
    best = None
    for sid, aname, slat, slon in areas:
        # cheap prefilter: 0.009° lat / 0.013° lon is >= 900 m anywhere in mainland
        # France, so nothing within the 800 m gate below is ever skipped.
        if abs(slat - lat) > 0.009 or abs(slon - lon) > 0.013:
            continue
        d = haversine(lat, lon, slat, slon)
        if d > 800:
            continue
        ns = name_score(name or "", aname)
        if national:
            ok = ns >= 0.5 or (ns > 0 and d <= 250)
            if ns < 0.75 and d > 400:
                ok = False  # a partial name far away is another stop (Mulhouse Zu Rhein)
        else:
            zid = sid.removeprefix("IDFM:")
            ztype = (zdc or {}).get(zid, {}).get("zdctype", "")
            ok = ns >= 0.5 or (ns > 0 and d <= 250 and ztype == "railStation")
        if not ok:
            continue
        key = (-ns, d)
        if best is None or key < best[0]:
            best = (key, sid, aname, d, ns)
    return None if best is None else best[1:]


@functools.lru_cache(maxsize=4)
def _cached_assign(places_sig: tuple, raw_dir_s: str, mtimes: tuple) -> dict[str, DeptAssignment]:
    raw_dir = Path(raw_dir_s)
    nat = _gtfs_areas(raw_dir / "sncf_national" / "sncf-gtfs.zip")
    freq: dict[str, tuple[str, str | None]] = {}
    try:
        rows = json.loads((raw_dir / "sncf_national" / "frequentation-gares.json").read_text(encoding="utf-8"))
        for r in rows:
            if r.get("code_uic_complet") and r.get("code_postal"):
                freq[_uic_norm(r["code_uic_complet"])] = (str(r["code_postal"]), r.get("direction_regionale_gares"))
    except OSError:
        pass
    idf = _gtfs_areas(raw_dir / "gtfs" / "IDFM-gtfs.zip")
    zdc: dict[str, dict] = {}
    try:
        with open(raw_dir / "idfm" / "zones-de-correspondance.csv", encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f, delimiter=";"):
                zdc[r["zdcid"]] = r
    except OSError:
        pass
    out: dict[str, DeptAssignment] = {}
    for uuid, name, lat, lon in places_sig:
        if lat is None or lon is None:
            continue
        hit = _best_match(name, lat, lon, nat, None, national=True)
        if hit is not None:
            sid, _, d, ns = hit
            uic = _uic_norm(sid.split(":")[-1].removeprefix("OCE"))
            row = freq.get(uic)
            if row is not None:
                cp, drg = row
                dept = dept_of_postal(cp)
                allowed = DRG_DEPARTMENTS.get(drg or "")
                ev = f"uic={uic} postal={cp} dist_m={d:.0f} name={ns:.2f}"
                if allowed is not None and dept not in allowed:
                    out[uuid] = DeptAssignment("", "QUARANTINED_DRG_MISMATCH", ev + f" drg={drg}")
                elif dept:
                    out[uuid] = DeptAssignment(dept, "UIC_POSTAL", ev)
                continue
        hit = _best_match(name, lat, lon, idf, zdc, national=False)
        if hit is not None:
            sid, _, d, ns = hit
            pr = zdc.get(sid.removeprefix("IDFM:"), {}).get("zdcpostalregion", "")
            dept = dept_of_postal(pr)
            if dept:
                out[uuid] = DeptAssignment(dept, "ZDC_POSTALREGION",
                                           f"zdc={sid.removeprefix('IDFM:')} postalregion={pr} "
                                           f"dist_m={d:.0f} name={ns:.2f}")
    return out


def assign_departments(places, raw_dir: Path) -> dict[str, DeptAssignment]:
    """Map station uuid -> département for stop places whose NeTEx id carries no INSEE code.

    Places that already carry an INSEE code are skipped (nothing to recover).
    Unmatched places get no entry; DRG-inconsistent ones are quarantined.
    Cached on the reference files' mtimes: twelve region builds in one process
    pay the matching cost once.
    """
    need = [(p.uuid, p.name or "", p.lat, p.lon) for p in places if not p.insee]
    if not need:
        return {}
    files = [raw_dir / "sncf_national" / "sncf-gtfs.zip", raw_dir / "sncf_national" / "frequentation-gares.json",
             raw_dir / "gtfs" / "IDFM-gtfs.zip", raw_dir / "idfm" / "zones-de-correspondance.csv"]
    mtimes = tuple((str(f), f.stat().st_mtime if f.exists() else None) for f in files)
    return _cached_assign(tuple(need), str(raw_dir), mtimes)
