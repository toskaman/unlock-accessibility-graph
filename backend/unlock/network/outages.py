"""Lift outages published in the IDFM traffic-information feed (PRIM, Navitia line_reports).

The feed carries one *disruption* per published message, tagged ``Ascenseur``, attached
to a stop area (an IDFM transfer zone) and to the lines that call there. The same lift
often has several active messages; UNLOCK groups them by the operator equipment id
found in ``reference`` (``GARES_CONNEXIONS_elevator_1090_…``, ``RATP_elevator_…``,
``SIRI_FM_RATP:LiftEquipment:…``).

Each outage is then placed on the network: which GTFS platforms lose a published
step-free route. The placement is deterministic and every link carries a derivation:

* ``DIRECTION_MATCH`` — metro/tram: the message names a direction that matches where
  that platform's trains go (terminus, headsign or a downstream station);
* ``LINE_AT_STATION`` — the message names no usable direction: every platform of the
  concerned line(s) at that station is marked;
* ``RAIL_STATION`` — RER/Transilien/TER: GTFS has one platform per mode and station.

Nothing is guessed about redundancy: the feed does not say whether another lift serves
the same platform. That is why the engine treats a reported outage as *removing
confirmation* (DOUBT), unless UNLOCK's station layer can evaluate it on real topology.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime

from ..ingest.spaces import normalize

_REF = [
    (re.compile(r"GARES_CONNEXIONS_elevator_(\d+)_"), "SNCF_GC", "GC:{}"),
    (re.compile(r"^RATP_elevator_(\d+)"), "RATP", "RATP:{}"),
    (re.compile(r"LiftEquipment:([^:]+):"), "RATP", "RATP-SIRI:{}"),
]
_DIR = re.compile(r"\b(?:direction|dir\.?)\s+([^,<>()]+?)(?=,|\.|<|>|$|\bjusqu|\bniveau|\bdirection\b)", re.I)
_UNTIL = re.compile(r"jusqu'?au\s+(\d{4}-\d{2}-\d{2})", re.I)
_METRO = re.compile(r"\b(?:ligne|m)\s*(\d{1,2}b?)\b", re.I)
_TRAM = re.compile(r"\b(?:t|tram(?:way)?\s*t?)\s*(\d{1,2}[ab]?)\b", re.I)
_RER = re.compile(r"\brer\s+([a-e])\b", re.I)
_STOP = {"de", "du", "des", "la", "le", "les", "d", "l", "sur", "et", "en", "gare", "porte", "saint", "st", "paris",
         "ville", "centre", "universite", "rer", "quai", "quais", "voie", "voies", "direction", "dir", "acces"}


def _clean(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()


def _ts(s: str | None) -> str | None:
    if not s:
        return None
    return datetime.strptime(s, "%Y%m%dT%H%M%S").strftime("%Y-%m-%dT%H:%M:%S")


def _toks(s: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", normalize(s)) if len(t) > 1 and t not in _STOP}


def lift_key(reference: str | None, disruption_id: str) -> tuple[str, str]:
    for rx, op, fmt in _REF:
        m = rx.search(reference or "")
        if m:
            return op, fmt.format(m.group(1))
    return "UNKNOWN", f"MSG:{disruption_id}"


def parse_line_reports(raw: dict) -> list[dict]:
    """Group active ``Ascenseur`` disruptions by lift. ``raw`` = {"fetched_at", "pages": [line_reports pages]}."""
    dis, links = {}, defaultdict(set)
    for page in raw["pages"]:
        for d in page.get("disruptions") or []:
            dis[d["id"]] = d
        for lr in page.get("line_reports") or []:
            line = lr["line"]
            for obj in [line] + (lr.get("pt_objects") or []):
                inner = obj.get(obj.get("embedded_type"), {}) or {}
                for l in (obj.get("links") or []) + (inner.get("links") or []):
                    if l.get("type") == "disruption":
                        links[l["id"]].add(line["id"].replace("line:", ""))
    groups: dict[str, dict] = {}
    for d in dis.values():
        if "Ascenseur" not in (d.get("tags") or []) or d.get("status") != "active":
            continue
        op, key = lift_key(d.get("reference"), d["id"])
        sa = next((o["pt_object"] for o in d.get("impacted_objects", []) if o["pt_object"].get("embedded_type") == "stop_area"), None)
        if not sa:
            continue
        text = max((_clean(m.get("text", "")) for m in d.get("messages", [])), key=len, default="")
        g = groups.setdefault(key, {"id": key, "operator": op, "station_zone_id": sa["id"].split(":")[-1],
                                    "stop_area_name": sa.get("name", ""), "texts": set(), "lines": set(),
                                    "first_reported": None, "last_update": None, "messages": 0, "disruption_ids": []})
        g["texts"].add(text)
        g["lines"] |= links.get(d["id"], set())
        b = _ts((d.get("application_periods") or [{}])[0].get("begin"))
        u = _ts(d.get("updated_at"))
        g["first_reported"] = min(filter(None, [g["first_reported"], b]), default=None)
        g["last_update"] = max(filter(None, [g["last_update"], u]), default=None)
        g["messages"] += 1
        g["disruption_ids"].append(d["id"])
    out = []
    for g in groups.values():
        texts = sorted(g.pop("texts"), key=lambda t: (-len(t), t))
        g["text"] = texts[0]
        m = _UNTIL.search(g["text"])
        g["announced_until"] = m.group(1) if m else None
        g["lines"] = sorted(g["lines"])
        g["disruption_ids"] = sorted(g["disruption_ids"])
        out.append(g)
    return sorted(out, key=lambda g: g["id"])


class Placer:
    """Map an outage onto network platforms (see module docstring for derivations)."""

    def __init__(self, network: dict):
        self.platforms = {p["id"]: p for p in network["platforms"]}
        self.stations = {s["id"]: s for s in network["stations"]}
        self.lines = {l["id"]: l for l in network["lines"]}
        self.by_station_line: dict[tuple[str, str], set[str]] = defaultdict(set)
        self.downstream: dict[tuple[str, str], set[str]] = defaultdict(set)   # (platform, line) -> where its trains go
        self.terminus: dict[tuple[str, str], set[str]] = defaultdict(set)
        for pat in network["patterns"]:
            stops = pat["stops"]
            for i, pid in enumerate(stops):
                st = self.platforms[pid]["station_id"]
                self.by_station_line[(st, pat["line_id"])].add(pid)
                if i < len(stops) - 1:
                    k = (pid, pat["line_id"])
                    self.terminus[k] |= _toks(self.stations[pat["terminus_station"]]["name"]) | _toks(pat["headsign"])
                    for q in stops[i + 1:]:
                        self.downstream[k] |= _toks(self.stations[self.platforms[q]["station_id"]]["name"])

    def _mode_hint(self, text: str, candidates: list[str]) -> list[str]:
        n = normalize(text)
        hinted = set()
        for num in _METRO.findall(n):
            hinted |= {l for l in candidates if self.lines[l]["mode"] == "METRO" and self.lines[l]["short_name"].lower() == num.lower()}
        for num in _TRAM.findall(n):
            hinted |= {l for l in candidates if self.lines[l]["mode"] == "TRAM" and self.lines[l]["short_name"].lower() == f"t{num.lower()}"}
        for x in _RER.findall(n):
            hinted |= {l for l in candidates if self.lines[l]["short_name"].lower() == x.lower()}
        return sorted(hinted)

    def place(self, outage: dict) -> dict:
        """Lines: those the text names; otherwise every line at the station (Gares & Connexions lifts: rail
        lines), narrowed to the lines whose trains go towards the named direction when one matches. The
        feed's own line links are not used: they are incomplete (independent check, docs/research/region_eval)."""
        st = outage["station_zone_id"]
        if st not in self.stations:
            return {"status": "STATION_NOT_IN_RAIL_NETWORK", "affects": []}
        at_station = sorted({l for (s, l) in self.by_station_line if s == st})
        hinted = self._mode_hint(outage["text"], at_station)
        if hinted:
            lines, line_how = hinted, "TEXT_NAMES_LINE"
        else:
            lines = at_station
            if outage["operator"] == "SNCF_GC":
                lines = [l for l in at_station if self.lines[l]["mode"] == "RAIL"] or at_station
            line_how = "ALL_LINES_AT_STATION"
        dirs = [d.strip() for d in _DIR.findall(outage["text"])]
        dir_toks = set().union(*(_toks(d) for d in dirs)) if dirs else set()

        def goes(p, l):
            k = (p, l)
            return bool(dir_toks & (self.terminus[k] | self.downstream[k]))

        if dir_toks and not hinted and len(lines) > 1:
            towards = [l for l in lines if any(goes(p, l) for p in self.by_station_line[(st, l)])]
            if 0 < len(towards) < len(lines):
                lines, line_how = towards, "DIRECTION_NAMES_LINE"
        affects = []
        for l in lines:
            pids = sorted(self.by_station_line[(st, l)])
            if self.lines[l]["mode"] == "RAIL":
                affects += [{"platform_id": p, "line_id": l, "derivation": "RAIL_STATION", "line_derivation": line_how}
                            for p in pids]
                continue
            chosen, how = pids, "LINE_AT_STATION"
            if dir_toks and len(pids) > 1:
                term = [p for p in pids if dir_toks & self.terminus[(p, l)]]
                down = [p for p in pids if goes(p, l)]
                pick = term if 0 < len(term) < len(pids) else (down if 0 < len(down) < len(pids) else [])
                if pick:
                    chosen, how = pick, "DIRECTION_MATCH"
            affects += [{"platform_id": p, "line_id": l, "derivation": how, "line_derivation": line_how} for p in chosen]
        uniq = {}
        for a in affects:
            uniq.setdefault((a["platform_id"], a["line_id"]), a)
        return {"status": "PLACED" if uniq else "NO_PLATFORM",
                "affects": sorted(uniq.values(), key=lambda a: (a["platform_id"], a["line_id"])), "directions": dirs}
