"""Rider alerts: is my usual trip still step-free today?

A trips file is JSON: {"trips": [{"label": "work", "from": "<station id or name>", "to": "...",
"usual": [optional legs {board, alight, line} as check_journey returns them]}]}.
Each run checks every trip against the best view, compares with the status stored by the previous run
(`last_status`), writes the new status back into the file and a timestamped report next to the bulletins.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def check(ns, trips: list[dict]) -> list[dict]:
    out = []
    for t in trips:
        a, b = ns.find_station(t["from"]), ns.find_station(t["to"])
        if not a or not b:
            out.append({**t, "status": "UNKNOWN_STATION", "message": f"Unknown station: {t['from'] if not a else t['to']}",
                        "from": {"name": t["from"]}, "to": {"name": t["to"]}})
            continue
        r = ns.trip_status(a, b, t.get("usual"))
        if t.get("label"):
            r["label"] = t["label"]
        r["previous_status"] = t.get("last_status")
        r["changed"] = t.get("last_status") is not None and t["last_status"] != r["status"]
        out.append(r)
    return out


def run_file(ns, path: Path, out_dir: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    res = check(ns, doc["trips"])
    for t, r in zip(doc["trips"], res):
        t["last_status"] = r["status"]
        if "usual" not in t and r.get("usual"):
            t["usual"] = [{k: l[k] for k in ("board", "alight", "line")} for l in r["usual"]]
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    rep = out_dir / f"alerts-{stamp}.json"
    rep.write_text(json.dumps({"checked_at": stamp, "trips": res}, ensure_ascii=False, indent=1, default=str),
                   encoding="utf-8", newline="\n")
    return {"trips": res, "report": rep}
