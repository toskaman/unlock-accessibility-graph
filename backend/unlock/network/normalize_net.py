"""Build the committed network snapshots from raw files.

* ``data/normalized/network.json``          — GTFS rail network + IDFM accessibility levels
* ``data/normalized/network_outages.json``  — PRIM lift outages grouped per lift and placed on platforms
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from ..config import MANIFEST_PATH, NORMALIZED_DIR, RAW_DIR
from .gtfs_net import build_network
from .outages import Placer, parse_line_reports

# IDFM "Accessibilité en gare" levels
ACCESS_LEVELS = {1: "NOT_ACCESSIBLE", 3: "ON_BOOKING_ASSISTENGARE", 4: "ON_REQUEST_AGENT", 6: "AUTONOMOUS"}


def boardable(p: dict) -> bool:
    """Wheelchair boarding declared by the publisher (GTFS) or by IDFM's station accessibility level."""
    if p.get("access_level") in ("ON_BOOKING_ASSISTENGARE", "ON_REQUEST_AGENT", "AUTONOMOUS"):
        return True
    if p.get("access_level") == "NOT_ACCESSIBLE":
        return False
    return p["wheelchair"] == "ACCESSIBLE"


def build_network_file(raw_dir: Path = RAW_DIR, out_dir: Path = NORMALIZED_DIR) -> dict:
    net = build_network(raw_dir / "gtfs" / "IDFM-gtfs.zip")
    acc_path = raw_dir / "idfm" / "accessibilite-en-gare.json"
    levels = {}
    if acc_path.exists():
        try:
            acc_rows = json.loads(acc_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            # A corrupt export must degrade the demo, not kill the build (the
            # fetcher validates first; this is the second line of defence).
            print(f"WARNING: ignoring unreadable {acc_path.name}: {e}", flush=True)
            acc_rows = []
        for r in acc_rows:
            levels[r["stop_point_id"].replace("stop_point:", "")] = ACCESS_LEVELS.get(r["accessibility_level_id"], "UNKNOWN")
    for p in net["platforms"]:
        if p["id"] in levels:
            p["access_level"] = levels[p["id"]]
        p["boardable"] = boardable(p)
    val_path = raw_dir / "idfm" / "validations-ferre-q2-2026.json"
    if val_path.exists():
        try:
            val_rows = json.loads(val_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            print(f"WARNING: ignoring unreadable {val_path.name}: {e}", flush=True)
            val_rows = []
        rows = {str(int(r["id_zdc"])): r for r in val_rows if r.get("id_zdc")}
        for st in net["stations"]:
            r = rows.get(st["id"])
            if r and r.get("d"):
                st["entries_per_day"] = round(r["v"] / r["d"])
                st["entries_days"] = r["d"]
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8")) if MANIFEST_PATH.exists() else {}
    net["datasets"] = [manifest[k] for k in ("idfm_gtfs", "idfm_accessibilite_en_gare", "idfm_validations_ferre")
                       if k in manifest]
    net["counts"] = {"stations": len(net["stations"]), "platforms": len(net["platforms"]), "lines": len(net["lines"]),
                     "patterns": len(net["patterns"]),
                     "boardable_platforms": sum(p["boardable"] for p in net["platforms"]),
                     "platforms_with_idfm_level": sum("access_level" in p for p in net["platforms"]),
                     "stations_with_entries": sum("entries_per_day" in s for s in net["stations"])}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "network.json").write_text(json.dumps(net, ensure_ascii=False, separators=(",", ":")), encoding="utf-8", newline="\n")
    return net


def build_outages_file(network: dict, raw_file: Path | None = None, out_dir: Path = NORMALIZED_DIR) -> dict | None:
    raw_file = raw_file or RAW_DIR / "prim" / "line_reports.json"
    if not raw_file.exists():
        return None
    raw = json.loads(raw_file.read_text(encoding="utf-8"))
    outages = parse_line_reports(raw)
    placer = Placer(network)
    q: Counter = Counter()
    for o in outages:
        placed = placer.place(o)
        o["placement"] = placed["status"]
        o["affects"] = placed["affects"]
        o["directions"] = placed.get("directions", [])
        q[f"operator_{o['operator']}"] += 1
        q[f"placement_{o['placement']}"] += 1
        for a in o["affects"]:
            q[f"affects_{a['derivation']}"] += 1
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8")) if MANIFEST_PATH.exists() else {}
    all_updates = [o["last_update"] for o in outages if o["last_update"]]
    doc = {"format": "unlock-outages/1", "observed_at": raw["fetched_at"], "source": raw.get("source"),
           "dataset": manifest.get("prim_lift_outages"),
           "feed_last_lift_update": max(all_updates) if all_updates else None,
           "feed_non_lift_last_update": _non_lift_last_update(raw),
           "counts": {"lifts": len(outages), "messages": sum(o["messages"] for o in outages), **dict(sorted(q.items()))},
           "outages": outages}
    (out_dir / "network_outages.json").write_text(json.dumps(doc, ensure_ascii=False, indent=0), encoding="utf-8", newline="\n")
    return doc


def _non_lift_last_update(raw: dict) -> str | None:
    best = None
    for page in raw["pages"]:
        for d in page.get("disruptions") or []:
            if "Ascenseur" not in (d.get("tags") or []) and d.get("updated_at"):
                best = max(best or d["updated_at"], d["updated_at"])
    if not best:
        return None
    return f"{best[0:4]}-{best[4:6]}-{best[6:8]}T{best[9:11]}:{best[11:13]}:{best[13:15]}"


def build(raw_dir: Path = RAW_DIR, out_dir: Path = NORMALIZED_DIR) -> dict:
    net = build_network_file(raw_dir, out_dir)
    out = build_outages_file(net, out_dir=out_dir)
    from . import idfm_lifts
    lifts = idfm_lifts.normalize_file(net, raw=raw_dir / "idfm" / "etat-des-ascenseurs.json", out=out_dir / "idfm_lifts.json")
    return {"network": net["counts"], "outages": out["counts"] if out else None,
            "idfm_lifts": lifts["counts"] if lifts else None}
