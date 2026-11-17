"""Lift-status history and headline metrics over time.

Every `python -m unlock record` (run by `refresh`) appends, to data/normalized/history/:

* ``sncf_lift_status.json`` — one observation per SNCF hourly-file version: every lift of France that is not
  available, with its state (lifts absent from an observation were AVAILABLE; the file lists every lift each time);
* ``metrics.json`` — per region and observation: confirmed / possible / published step-free journeys, points cut
  or in doubt, lifts out, and the state of every station that is not fully open (for the time-lapse map).

(IDFM's own history stays in ``idfm_lift_history.json``, written by `fetch-lifts`.)
Analyses (outage durations, chronic lifts, journeys lost per day) read only these files.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import MANIFEST_PATH, NORMALIZED_DIR, RAW_DIR

HIST = NORMALIZED_DIR / "history"
SNCF_STATUS = {"OK": "AVAILABLE", "KO": "UNAVAILABLE", "INCONNU": "UNKNOWN"}


def _load(path: Path, empty: dict) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else empty


def _save(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=0, sort_keys=False), encoding="utf-8", newline="\n")


def sncf_observation(raw: Path = RAW_DIR / "sncf" / "etat-fonctionnement-elevatique-gare.csv",
                     manifest_path: Path = MANIFEST_PATH) -> dict | None:
    if not raw.exists():
        return None
    body = raw.read_bytes()
    m = _load(manifest_path, {}).get("sncf_lift_status", {})
    na, n = {}, 0
    with open(raw, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            n += 1
            st = SNCF_STATUS.get((r.get("etat_de_fonctionnement") or "").strip().upper(), "UNKNOWN")
            if st != "AVAILABLE":
                na[r["id"]] = st
    return {"observed_at": m.get("publisher_modified") or m.get("retrieved_at"), "retrieved_at": m.get("retrieved_at"),
            "sha256": hashlib.sha256(body).hexdigest(), "lifts": n, "not_available": dict(sorted(na.items()))}


def append_sncf(obs: dict | None, path: Path | None = None) -> dict:
    path = path or HIST / "sncf_lift_status.json"
    doc = _load(path, {"format": "unlock-sncf-lift-history/1", "observations": []})
    if obs and not any(o["sha256"] == obs["sha256"] for o in doc["observations"]):
        doc["observations"].append(obs)
        doc["observations"].sort(key=lambda o: o["observed_at"] or "")
        _save(path, doc)
    return doc


def region_metrics(ns, code: str) -> dict[str, Any]:
    """Headline numbers of one region's NetworkService, as stored in metrics.json."""
    from .network.idfm_lifts import night_window
    ov = ns.overview()
    v, p, f = ov["views"]["best"], ov["views"]["published"], ov["views"]["feed"]
    sncf_at = (ns.ss.snapshot or {}).get("observed_at")
    idfm = ov.get("idfm_status") or {}
    stations = {s["id"]: s["state"] for s in ns.map_layer("best")["stations"] if s["state"] in ("CLOSED", "DOUBT")}
    return {
        "region": code, "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sncf_observed_at": sncf_at, "idfm_observed_at": idfm.get("observed_at"),
        "night": bool(night_window(sncf_at) or (idfm.get("observed_at") and night_window(idfm["observed_at"]))),
        "published": p["confirmed"], "confirmed": v["confirmed"], "possible": v["possible"],
        "feed_confirmed": f["confirmed"] if ov.get("has_feed") else None,
        "points_closed": v["boarding_points"]["closed"], "points_doubt": v["boarding_points"]["doubt"],
        "stations_affected": v["stations_affected"],
        "sncf_lifts_out": sum(1 for s in ns.ss.baseline_state.values() if s.value == "UNAVAILABLE"),
        "sncf_lifts_unknown": sum(1 for s in ns.ss.baseline_state.values() if s.value == "UNKNOWN"),
        "ratp_lifts_out": idfm.get("ratp_unavailable"), "ratp_lifts_unknown": idfm.get("ratp_unknown"),
        "night_closure_suspected": idfm.get("night_closure_suspected"),
        "journeys_hidden_by_stale_messages": (ov.get("stale_messages") or {}).get("journeys_hidden"),
        "station_states": stations,
    }


def append_metrics(rows: list[dict], path: Path | None = None) -> dict:
    path = path or HIST / "metrics.json"
    doc = _load(path, {"format": "unlock-metrics-history/1", "observations": []})
    seen = {(o["region"], o["sncf_observed_at"], o["idfm_observed_at"]) for o in doc["observations"]}
    for r in rows:
        k = (r["region"], r["sncf_observed_at"], r["idfm_observed_at"])
        if k not in seen:
            doc["observations"].append(r)
            seen.add(k)
    doc["observations"].sort(key=lambda o: (o["region"], o["sncf_observed_at"] or "", o["idfm_observed_at"] or ""))
    _save(path, doc)
    return doc


# ----------------------------------------------------------------------------------------------- analyses
def outage_spells(observations: list[dict], key: str = "not_available") -> dict[str, list[dict]]:
    """Per lift, the spells during which it was not available: [{start, end, observations, still_out}].
    A spell starts at the first observation listing the lift and ends at the first later observation that does
    not (its time is the end bound). Times are observation times, so durations are bounded by fetch frequency."""
    obs = sorted(observations, key=lambda o: o["observed_at"] or "")
    spells: dict[str, list[dict]] = defaultdict(list)
    open_: dict[str, dict] = {}
    for o in obs:
        cur = o[key]
        for lid in cur:
            if lid not in open_:
                open_[lid] = {"start": o["observed_at"], "end": None, "observations": 0, "states": set()}
            open_[lid]["observations"] += 1
            st = cur[lid][0] if isinstance(cur[lid], list) else cur[lid]
            open_[lid]["states"].add(st)
        for lid in list(open_):
            if lid not in cur:
                s = open_.pop(lid)
                s["end"] = o["observed_at"]
                spells[lid].append(s)
    for lid, s in open_.items():
        spells[lid].append(s)
    for lid in spells:
        for s in spells[lid]:
            s["still_out"] = s["end"] is None
            s["states"] = sorted(s["states"])
    return dict(spells)


def share_out(observations: list[dict], key: str = "not_available", state: str = "UNAVAILABLE") -> dict[str, float]:
    """Fraction of observations in which each lift was in `state` (chronic lifts: high share over many weeks)."""
    n = len(observations)
    if not n:
        return {}
    c: dict[str, int] = defaultdict(int)
    for o in observations:
        for lid, v in o[key].items():
            st = v[0] if isinstance(v, list) else v
            if st == state:
                c[lid] += 1
    return {lid: round(k / n, 4) for lid, k in sorted(c.items())}


def summary(hist_dir: Path | None = None, min_days_for_chronic: float = 7.0) -> dict[str, Any]:
    """What the recorded history can already say — and how much of it there is."""
    hist_dir = hist_dir or HIST
    sn = _load(hist_dir / "sncf_lift_status.json", {"observations": []})["observations"]
    me = _load(hist_dir / "metrics.json", {"observations": []})["observations"]
    span = None
    if len(sn) > 1:
        t = [datetime.fromisoformat(o["observed_at"]) for o in sn if o["observed_at"]]
        span = round((max(t) - min(t)).total_seconds() / 86400, 2)
    by_region: dict[str, list[dict]] = defaultdict(list)
    for o in me:
        by_region[o["region"]].append({k: o[k] for k in ("sncf_observed_at", "idfm_observed_at", "night", "published",
                                                         "confirmed", "possible", "points_closed", "stations_affected")})
    out = {"sncf_observations": len(sn), "span_days": span, "metrics_by_region": dict(by_region)}
    if span and span >= min_days_for_chronic:
        sh = share_out(sn)
        out["chronic_sncf_lifts"] = {k: v for k, v in sh.items() if v >= 0.3}
    return out


def region_series(code: str, hist_dir: Path | None = None) -> dict[str, Any]:
    """The recorded headline numbers of one region, oldest first (what the UI's history chart draws)."""
    hist_dir = hist_dir or HIST
    me = _load(hist_dir / "metrics.json", {"observations": []})["observations"]
    rows = [{k: o.get(k) for k in ("recorded_at", "sncf_observed_at", "idfm_observed_at", "night", "published",
                                   "confirmed", "possible", "points_closed", "stations_affected", "sncf_lifts_out",
                                   "ratp_lifts_out")}
            for o in me if o["region"] == code]
    rows.sort(key=lambda r: max(r["sncf_observed_at"] or "", r["idfm_observed_at"] or ""))
    return {"region": code, "observations": rows}
