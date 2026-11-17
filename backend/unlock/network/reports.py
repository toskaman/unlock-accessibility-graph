"""Field reports: what riders, staff and AI agents see on site, kept in the Relate graph next to the official status.

A report is a (:FieldReport) node linked [:ABOUT] to the lift it concerns (an IDFM « État des ascenseurs » lift or a
lift of the SNCF station layer) and [:AT] to the network station. It is a shared memory: one agent (or rider) writes
it, every other agent and the web app read it back through the graph.

A report never changes the official status or any journey count. UNLOCK only sets it against the official status
of the same lift — the one the best view uses (SNCF's hourly file for SNCF lifts, IDFM's dataset for the others):
CONFIRMS, CONTRADICTS, or NEW_INFO when it is unknown. When IDFM's dataset also lists an SNCF lift, its status is
given too (`other_official`), because the two official sources sometimes disagree. Reports older than
RECENT_HOURS are shown as old. Writes go through the one process that owns the store (the API server): Relate allows
a single writer, and every agent shares that graph through it.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

STATUSES = ("OUT", "WORKING")
SOURCES = ("rider", "staff", "agent")
RECENT_HOURS = 12
MAX_NOTE = 280
MAX_REPORTER = 60


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def lift_info(ns, lift_id: str) -> dict[str, Any] | None:
    """The lift as UNLOCK knows it: station, operator, label and the official status with its time — the same
    status the best view uses: SNCF's hourly file for SNCF lifts, IDFM « État des ascenseurs » for the others."""
    if lift_id in ns.ss.lifts:
        l = ns.ss.lifts[lift_id]
        sid = next((n for n, sn in ns.sncf_of.items() if l.station_id in sn), None)
        if sid is None and lift_id in ns.idfm_lifts:
            sid = ns.idfm_lifts[lift_id]["zdc"]
        info = {"lift": lift_id, "kind": "Lift", "station_id": sid, "operator": "SNCF",
                "label": " — ".join(x for x in (l.name, l.description) if x) or lift_id,
                "official_status": ns.ss.baseline_state[lift_id].value if lift_id in ns.ss.baseline_state else "UNKNOWN",
                "official_source": "SNCF hourly lift status", "official_updated": (ns.ss.snapshot or {}).get("observed_at")}
        if lift_id in ns.idfm_lifts:   # IDFM's dataset lists the same lift: say so when the two official sources differ
            i = ns.idfm_lifts[lift_id]
            info["other_official"] = {"source": "IDFM « État des ascenseurs »", "status": i["status"], "updated": i.get("updated"),
                                      "agrees": i["status"] == info["official_status"]}
        return info
    if lift_id in ns.idfm_lifts:
        l = ns.idfm_lifts[lift_id]
        return {"lift": lift_id, "kind": "IdfmLift", "station_id": l["zdc"], "operator": l["operator"],
                "label": l.get("direction") or lift_id, "official_status": l["status"],
                "official_source": "IDFM « État des ascenseurs »", "official_updated": l.get("updated")}
    return None


def verdict(status: str, official: str) -> str:
    if official not in ("AVAILABLE", "UNAVAILABLE"):
        return "NEW_INFO"
    return "CONFIRMS" if (status == "OUT") == (official == "UNAVAILABLE") else "CONTRADICTS"


def add(ns, lift_id: str, status: str, note: str = "", source: str = "rider", reporter: str = "",
        now: datetime | None = None) -> dict[str, Any]:
    """Store one report in the graph. Raises ValueError (bad input) or KeyError (unknown lift)."""
    status, source = (status or "").upper(), (source or "").lower()
    if status not in STATUSES:
        raise ValueError(f"status must be one of {', '.join(STATUSES)}")
    if source not in SOURCES:
        raise ValueError(f"source must be one of {', '.join(SOURCES)}")
    note, reporter = (note or "").strip(), (reporter or "").strip()
    if len(note) > MAX_NOTE or len(reporter) > MAX_REPORTER:
        raise ValueError(f"note ≤ {MAX_NOTE} characters, reporter ≤ {MAX_REPORTER}")
    info = lift_info(ns, lift_id)
    if info is None:
        raise KeyError(lift_id)
    at = (now or _now()).isoformat()
    rid = "fr-" + hashlib.sha256(f"{lift_id}|{status}|{at}|{reporter}|{note}".encode()).hexdigest()[:16]
    ns.db.query(f"""MATCH (l:{info['kind']} {{id: $lift}})
        MERGE (r:FieldReport {{id: $id}})
        SET r.lift = $lift, r.status = $status, r.note = $note, r.source = $source, r.reporter = $reporter,
            r.reported_at = $at, r.official_status = $official, r.official_updated = $updated
        MERGE (r)-[:ABOUT]->(l)""",
                {"lift": lift_id, "id": rid, "status": status, "note": note, "source": source, "reporter": reporter,
                 "at": at, "official": info["official_status"], "updated": info["official_updated"]})
    if info["station_id"]:
        ns.db.query("""MATCH (r:FieldReport {id: $id}) MATCH (s:NStation {id: $sid}) MERGE (r)-[:AT]->(s)""",
                    {"id": rid, "sid": info["station_id"]})
    return next(r for r in reports(ns, hours=24 * 365) if r["id"] == rid)


def reports(ns, station_id: str | None = None, hours: float = 24, now: datetime | None = None) -> list[dict[str, Any]]:
    """Reports of the last `hours`, newest first, each set against the lift's official status today."""
    t = now or _now()
    since = (t - timedelta(hours=hours)).isoformat()
    rows = ns.db.query("""MATCH (r:FieldReport)-[:ABOUT]->(l) WHERE r.reported_at >= $since
        RETURN r.id AS id, r.lift AS lift, r.status AS status, r.note AS note, r.source AS source,
               r.reporter AS reporter, r.reported_at AS reported_at ORDER BY reported_at DESC""", {"since": since})
    out = []
    for r in rows:
        info = lift_info(ns, r["lift"]) or {"station_id": None, "operator": None, "label": r["lift"],
                                              "official_status": "UNKNOWN", "official_source": None, "official_updated": None}
        if station_id and info["station_id"] != station_id:
            continue
        age_h = (t - datetime.fromisoformat(r["reported_at"])).total_seconds() / 3600
        st = ns.stations.get(info["station_id"] or "", {})
        out.append({**r, "station_id": info["station_id"], "station": st.get("name"), "operator": info["operator"],
                    "label": info["label"], "official_status": info["official_status"],
                    "official_source": info["official_source"], "official_updated": info["official_updated"],
                    **({"other_official": info["other_official"]} if info.get("other_official") else {}),
                    "verdict": verdict(r["status"], info["official_status"]),
                    "age_hours": round(age_h, 1), "recent": age_h <= RECENT_HOURS})
    return out


def summary(rows: list[dict]) -> dict[str, Any]:
    """What a maintenance team should look at first: recent reports that contradict or add to the official status."""
    recent = [r for r in rows if r["recent"]]
    return {"reports": len(rows), "recent": len(recent),
            "contradicts_official": sum(r["verdict"] == "CONTRADICTS" for r in recent),
            "confirms_official": sum(r["verdict"] == "CONFIRMS" for r in recent),
            "new_info": sum(r["verdict"] == "NEW_INFO" for r in recent),
            "check_first": [r for r in recent if r["verdict"] != "CONFIRMS"][:10],
            "rule": "A field report never changes the official status or any journey count; it is set against it."}
