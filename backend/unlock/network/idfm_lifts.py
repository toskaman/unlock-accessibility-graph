"""IDFM « État des ascenseurs » — the lift inventory and current status for RATP (and SNCF) stations.

Unlike the PRIM traffic messages, this dataset lists every lift (working or not), its status refreshed several
times a day, and a structured ``liftDirection`` such as
``"Ligne M4 direction Porte de Clignancourt  /  Accès 1 avenue Max Dormoy"`` — the levels the lift joins.
UNLOCK turns each RATP station into a small graph, exactly like its SNCF station layer:

* nodes: the street (``ACCESS``), named intermediate spaces (``salle d'échange``…) and the network boarding points
  (platform × line) a side designates — line from the text, platform direction matched against GTFS;
* edges: lifts, between every pair of the sides they list.

A boarding point is then OPEN if the street reaches it through available lifts, DOUBT if only through lifts of
unknown status, CLOSED if every route needs a lift that is out of service; points whose lifts never connect to the
street in the published text keep the plain rule "a lift touching it is out → DOUBT". Every side keeps its
derivation. Needs a personal Opendatasoft key (UNLOCK_IDFM_ODS_KEY or UNLOCK_IDFM_ODS_KEY_FILE).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.request
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

from ..config import MANIFEST_PATH, NORMALIZED_DIR, RAW_DIR
from ..ingest.spaces import normalize
from .outages import Placer, _toks

URL = ("https://data.iledefrance-mobilites.fr/api/explore/v2.1/catalog/datasets/etat-des-ascenseurs/exports/json")
RAW = RAW_DIR / "idfm" / "etat-des-ascenseurs.json"
OUT = NORMALIZED_DIR / "idfm_lifts.json"
HISTORY = NORMALIZED_DIR / "idfm_lift_history.json"

_LINE = re.compile(r"\b(?:ligne|metro|m|l)\s*(?:m\s*)?(\d{1,2}(?:\s?bis)?)\b|\brer\s+([a-e])\b|\b(t\d{1,2}[ab]?)\b", re.I)
_ACCESS = re.compile(r"\b(acces|sortie|rue|avenue|av\.|place|boulevard|bd|parvis|entree|surface|voirie|gare routiere|"
                     r"esplanade|square|cours|chemin|allee|route|rond-point|exterieur)\b", re.I)
STATUS = {"available": "AVAILABLE", "notavailable": "UNAVAILABLE", "unknown": "UNKNOWN"}


def key() -> str:
    k = os.environ.get("UNLOCK_IDFM_ODS_KEY", "").strip()
    p = os.environ.get("UNLOCK_IDFM_ODS_KEY_FILE", "").strip()
    if not k and p:
        k = Path(p).read_text(encoding="utf-8").strip()
    if not k:
        raise SystemExit("No Opendatasoft key: set UNLOCK_IDFM_ODS_KEY or UNLOCK_IDFM_ODS_KEY_FILE "
                         "(data.iledefrance-mobilites.fr → account → API keys). UNLOCK runs on the committed snapshot.")
    return k


def fetch(dest: Path = RAW) -> Path:
    req = urllib.request.Request(URL, headers={"Authorization": "Apikey " + key(), "User-Agent": "UNLOCK-hackathon/0.6"})
    with urllib.request.urlopen(req, timeout=120) as r:
        body = r.read()
    dest.parent.mkdir(parents=True, exist_ok=True)
    fetched = datetime.now(timezone.utc).isoformat(timespec="seconds")
    dest.write_bytes(json.dumps({"fetched_at": fetched, "records": json.loads(body)}, ensure_ascii=False).encode("utf-8"))
    m = json.loads(MANIFEST_PATH.read_text(encoding="utf-8")) if MANIFEST_PATH.exists() else {}
    m["idfm_etat_ascenseurs"] = {"key": "idfm_etat_ascenseurs", "title": "État des ascenseurs", "publisher": "Île-de-France Mobilités",
                                 "url": URL, "file": "idfm/etat-des-ascenseurs.json", "bytes": len(body),
                                 "sha256": hashlib.sha256(body).hexdigest(), "retrieved_at": fetched,
                                 "publisher_modified": None, "licence": "Licence Mobilités",
                                 "licence_url": "https://prim.iledefrance-mobilites.fr/fr/licences",
                                 "role": "Every lift of RATP and SNCF stations in IDF with its current status and the levels it joins"}
    MANIFEST_PATH.write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n")
    return dest


def classify_side(text: str) -> tuple[str, list[tuple[str | None, str | None]]]:
    """→ (kind, [(line_token, direction_text)]); kind ∈ PLATFORM, ACCESS, SPACE, EMPTY."""
    s = normalize(text or "").strip(" .,")
    if not s:
        return "EMPTY", []
    lines = []
    for m in _LINE.finditer(s):
        tok = (m.group(1) or m.group(2) or m.group(3) or "").replace(" ", "").lower()
        lines.append(tok)
    if lines:
        d = re.search(r"direction\s+(.+)$", s)
        return "PLATFORM", [(t, d.group(1).strip() if d and len(lines) == 1 else None) for t in lines]
    if _ACCESS.search(s):
        return "ACCESS", []
    return "SPACE", []


class LiftPlacer(Placer):
    def line_ids(self, st: str, tok: str) -> list[str]:
        at = sorted({l for (s, l) in self.by_station_line if s == st})
        tok = tok.lower()
        out = []
        for l in at:
            sn = self.lines[l]["short_name"].lower().replace(" ", "")
            if sn == tok or (self.lines[l]["mode"] == "TRAM" and sn == tok):
                out.append(l)
        return out

    def points(self, st: str, tok: str, direction: str | None) -> tuple[list[tuple[str, str]], str]:
        pts, how = [], "LINE_AT_STATION"
        for l in self.line_ids(st, tok):
            pids = sorted(self.by_station_line[(st, l)])
            chosen = pids
            dt = _toks(direction) if direction else set()
            if dt and len(pids) > 1:
                term = [p for p in pids if dt & self.terminus[(p, l)]]
                down = [p for p in pids if dt & (self.terminus[(p, l)] | self.downstream[(p, l)])]
                pick = term if 0 < len(term) < len(pids) else (down if 0 < len(down) < len(pids) else [])
                if pick:
                    chosen, how = pick, "DIRECTION_MATCH"
            pts += [(p, l) for p in chosen]
        return pts, how if pts else "NO_MATCH"


def paris_local(utc: datetime) -> datetime:
    """UTC → Paris wall-clock time (CET/CEST, EU rule: last Sunday of March/October at 01:00 UTC) without tzdata."""
    from datetime import timedelta

    def last_sunday(y, m):
        d = datetime(y, m + 1, 1, tzinfo=timezone.utc) - timedelta(days=1)
        return d - timedelta(days=(d.weekday() + 1) % 7)
    y = utc.year
    summer = last_sunday(y, 3).replace(hour=1) <= utc < last_sunday(y, 10).replace(hour=1)
    return (utc + timedelta(hours=2 if summer else 1)).replace(tzinfo=None)


NIGHT_START, NIGHT_END = 23, 6   # Paris time; metro/RER service ends ~01:15 and lifts are switched off with it


def night_window(observed_at: str | None):
    """If the snapshot was taken at night, the Paris-local time from which a new 'notavailable' is suspect."""
    if not observed_at:
        return None
    from datetime import timedelta
    loc = paris_local(datetime.fromisoformat(observed_at).astimezone(timezone.utc))
    if not (loc.hour >= NIGHT_START or loc.hour < NIGHT_END):
        return None
    start = loc.replace(hour=NIGHT_START, minute=0, second=0, microsecond=0)
    return start if loc.hour >= NIGHT_START else start - timedelta(days=1)


def normalize_file(network: dict, raw: Path = RAW, out: Path = OUT) -> dict | None:
    if not raw.exists():
        return None
    doc = json.loads(raw.read_text(encoding="utf-8"))
    recs = doc["records"] if isinstance(doc, dict) else doc
    placer = LiftPlacer(network)
    lifts = []
    night = night_window(doc.get("fetched_at") if isinstance(doc, dict) else None)
    for x in recs:
        op = "RATP" if x["liftid"].startswith("RATP") else "SNCF"
        sides = []
        for i, side in enumerate(re.split(r"\s+/\s+", x.get("liftdirection") or "")):
            kind, toks = classify_side(side)
            s = {"index": i, "text": side.strip(), "kind": kind}
            if kind == "PLATFORM":
                pts, how = [], "NO_MATCH"
                for tok, direction in toks:
                    p, h = placer.points(x["zdcid"], tok, direction)
                    pts += p
                    how = h if p else how
                s["points"] = [{"platform_id": p, "line_id": l} for p, l in dict.fromkeys(pts)]
                s["derivation"] = how
            elif kind == "SPACE":
                s["space"] = re.split(r"[,.(]| - | secteur | section ", normalize(side))[0].strip()
            sides.append(s)
        status, note = STATUS.get(x.get("liftstatus"), "UNKNOWN"), None
        upd = x.get("liftstateupdate")
        if night and status == "UNAVAILABLE" and upd and datetime.fromisoformat(upd[:16]) >= night:
            # switched off since 23:00 while the snapshot itself is a night one: end-of-service shutdown is far
            # more likely than a breakdown — reported as UNKNOWN, never as a confirmed outage
            status, note = "UNKNOWN", "NIGHT_CLOSURE_SUSPECTED"
        lifts.append({"id": x["liftid"], "operator": op, "zdc": x["zdcid"], "zdc_name": x.get("zdcname"),
                      "status": status, "status_note": note, "raw_status": x.get("liftstatus"),
                      "reason": x.get("liftreason"),
                      "updated": x.get("liftstateupdate"), "mode": x.get("liftmode"),
                      "direction": x.get("liftdirection"), "situation": x.get("liftsituation"),
                      "private_id": x.get("privateelevatorid"), "sides": sides})
    res = {"format": "unlock-idfm-lifts/1", "observed_at": doc.get("fetched_at") if isinstance(doc, dict) else None,
           "counts": {"lifts": len(lifts), "ratp": sum(l["operator"] == "RATP" for l in lifts),
                      "ratp_unavailable": sum(l["operator"] == "RATP" and l["status"] == "UNAVAILABLE" for l in lifts),
                      "ratp_unknown": sum(l["operator"] == "RATP" and l["status"] == "UNKNOWN" for l in lifts),
                      "night_closure_suspected": sum(l["status_note"] == "NIGHT_CLOSURE_SUSPECTED" for l in lifts),
                      "ratp_sides_placed": sum(1 for l in lifts if l["operator"] == "RATP" for s in l["sides"]
                                               if s["kind"] == "PLATFORM" and s["points"])},
           "lifts": lifts}
    out.write_text(json.dumps(res, ensure_ascii=False, indent=0), encoding="utf-8", newline="\n")
    append_history(res, out.parent / HISTORY.name)
    return res


def append_history(doc: dict, path: Path = HISTORY) -> dict:
    """Keep one compact observation per fetch: every lift NOT available, with its status and update time.
    Lifts absent from an observation were AVAILABLE then (all lifts of the dataset are listed every time)."""
    hist = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"format": "unlock-idfm-lift-history/1",
                                                                                "observations": []}
    obs = {"observed_at": doc["observed_at"], "lifts": doc["counts"]["lifts"],
           "not_available": {l["id"]: [l["status"], l["updated"]] for l in doc["lifts"] if l["status"] != "AVAILABLE"}}
    if not any(o["observed_at"] == obs["observed_at"] for o in hist["observations"]):
        hist["observations"].append(obs)
        hist["observations"].sort(key=lambda o: o["observed_at"] or "")
        path.write_text(json.dumps(hist, ensure_ascii=False, indent=0), encoding="utf-8", newline="\n")
    return hist


def changes(prev: dict | None, cur: dict) -> dict:
    """Lifts newly out / back in service between two history observations."""
    if not prev:
        return {"since": None, "newly_out": [], "back_in_service": [], "still_out": sorted(cur["not_available"])}
    p, c = prev["not_available"], cur["not_available"]
    return {"since": prev["observed_at"],
            "newly_out": sorted(k for k in c if k not in p or p[k][0] != c[k][0] and c[k][0] == "UNAVAILABLE"),
            "back_in_service": sorted(k for k in p if k not in c),
            "still_out": sorted(k for k in c if k in p and p[k][0] == c[k][0])}


def point_states(lifts: list[dict], status: dict[str, str], rail_lines: set[str] = frozenset()) -> dict[str, tuple[str, str]]:
    """RATP station topology → {point "platform|line": (state, derivation)} for points some RATP lift touches."""
    by_station = defaultdict(list)
    for l in lifts:
        if l["operator"] == "RATP":
            by_station[l["zdc"]].append(l)
    out: dict[str, tuple[str, str]] = {}
    for st, ls in by_station.items():
        edges = []   # (lift id, [nodes])
        touch = defaultdict(list)
        for l in ls:
            nodes = []
            for s in l["sides"]:
                if s["kind"] == "ACCESS":
                    nodes.append("ACCESS")
                elif s["kind"] == "SPACE":
                    nodes.append("SPACE:" + s["space"])
                elif s["kind"] == "PLATFORM":
                    for p in s.get("points", []):
                        k = f"{p['platform_id']}|{p['line_id']}"
                        nodes.append(k)
                        touch[k].append(l["id"])
            edges.append((l["id"], sorted(set(nodes))))

        def reach(ok: set[str]) -> set[str]:
            adj = defaultdict(set)
            for lid, ns in edges:
                if lid in ok:
                    for a in ns:
                        adj[a] |= set(ns) - {a}
            seen, dq = {"ACCESS"}, deque(["ACCESS"])
            while dq:
                n = dq.popleft()
                for m in adj[n] - seen:
                    seen.add(m)
                    dq.append(m)
            return seen

        ids = [l["id"] for l in ls]
        r_all = reach(set(ids))
        r_now = reach({i for i in ids if status.get(i) == "AVAILABLE"})
        r_maybe = reach({i for i in ids if status.get(i) in ("AVAILABLE", "UNKNOWN")})
        for k, touching in touch.items():
            if k in r_all:
                state = "OPEN" if k in r_now else "DOUBT" if k in r_maybe else "CLOSED"
                how = "STATION_LIFT_GRAPH"
                if state == "OPEN" and k.split("|")[1] in rail_lines and any(status.get(i) != "AVAILABLE" for i in touching):
                    # one GTFS node stands for several RER platforms: a lift out means some of them are cut
                    state, how = "DOUBT", "SOME_RAIL_PLATFORMS_CUT"
                out[k] = (state, how)
            else:
                bad = any(status.get(i) != "AVAILABLE" for i in touching)
                out[k] = ("DOUBT" if bad else "OPEN", "LIFT_TOUCHES_PLATFORM")
    return out
