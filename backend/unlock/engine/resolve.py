"""Graph-grounded incident resolution: free text -> one lift in the Relate graph.

Operators and travellers report outages in free text ("Juvisy : ascenseur quai 50/51
HS depuis ce matin"). Turning that into an exact equipment id is where a plain LLM
guesses. UNLOCK resolves it deterministically against connected context read from
Relate:

* station candidates from ``Station.name`` **and** the IDFM transfer-zone name the
  station is linked to (``IN_TRANSFER_ZONE``), so "Gare de l'Est" finds "Paris Est";
* lift candidates from what each lift actually ``SERVES`` in the graph — the platforms
  (track codes) and named spaces (souterrain nord, sortie Seine…) — plus its number.

It returns RESOLVED only when one lift clearly wins; otherwise AMBIGUOUS with the
candidates and the question to ask. It never invents an id: every candidate is a node
that exists in the store, with the evidence that matched.
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from ..db import GraphStore
from ..ingest.spaces import normalize

Q_LIFT_CONTEXT = """
MATCH (s:Station)-[:HAS_LIFT]->(l:Lift)
OPTIONAL MATCH (s)-[:IN_TRANSFER_ZONE]->(z:TransferZone)
OPTIONAL MATCH (l)-[:SERVES]->(sp:Space)
OPTIONAL MATCH (sp)-[:IS_PLATFORM_OF]->(q:Quay)
RETURN s.id AS station_id, s.name AS station, z.name AS zone, l.id AS lift_id, l.name AS lift_name,
       l.description AS description,
       collect(DISTINCT CASE WHEN q IS NULL THEN null ELSE q.code END) AS codes,
       collect(DISTINCT CASE WHEN sp.role IN ['UNSPECIFIED'] OR q IS NOT NULL THEN null ELSE sp.name END) AS spaces
ORDER BY station_id, lift_id
"""

STOP = {"gare", "de", "du", "des", "la", "le", "les", "d", "l", "sur", "et", "en", "rer", "sncf", "station", "a", "au",
        "aux", "the", "at", "of", "in", "on", "paris", "saint", "st", "ville", "centre", "sous"}
GENERIC = {"ascenseur", "ascenseurs", "asc", "lift", "elevator", "pmr", "panne", "hs", "ko", "quai", "quais", "voie",
           "voies", "depuis", "matin", "ce", "est", "service", "hors", "broken", "out", "is", "platform", "platforms",
           "track", "tracks", "acces", "bloque", "bloquee", "arret", "remis", "fonctionne", "toujours", "encore",
           "signale", "signalement", "usager", "usagers", "fauteuil", "roulant", "mon", "ma", "nous", "on", "pour",
           "pas", "ne", "plus", "un", "une"}
DOWN = ("hors service", "en panne", "panne", " hs", "ko", "bloque", "broken", "out of order", "out of service",
        "ne fonctionne pas", "ne marche pas", "arret", "en derangement", "inaccessible")
UP = ("remis en service", "fonctionne a nouveau", "repare", "back in service", "working again", "retabli")
_PAIR = re.compile(r"\b(?:voies?|quais?|v|platforms?|tracks?)\s*([0-9]{1,2}[a-z]?|[a-k])\s*(?:/|-|et|and|&|,)\s*([0-9]{1,2}[a-z]?|[a-k])\b")
_SINGLE = re.compile(r"\b(?:voies?|quais?|v|platforms?|tracks?)\s*([0-9]{1,2}[a-z]?|[a-k])\b")
_NUM = re.compile(r"\b(\d{4})\b")
_ASCN = re.compile(r"\bas[c]?\s*(\d{1,2})\b")


def _tokens(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", normalize(text)) if t and t not in STOP and len(t) > 1]


@dataclass
class LiftDoc:
    lift_id: str
    station_id: str
    station: str
    name: str
    description: str
    codes: set[str]
    space_tokens: set[str]
    number: str | None
    asc_n: str | None


@dataclass
class Index:
    stations: dict[str, dict] = field(default_factory=dict)       # id -> {name, aliases:[...], tokens:set}
    lifts: dict[str, list[LiftDoc]] = field(default_factory=dict)  # station id -> lifts
    idf: dict[str, float] = field(default_factory=dict)


def build_index(db: GraphStore) -> Index:
    ix = Index()
    for r in db.query(Q_LIFT_CONTEXT):
        st = ix.stations.setdefault(r["station_id"], {"name": r["station"], "aliases": set()})
        st["aliases"].add(r["station"])
        if r["zone"]:
            st["aliases"].add(r["zone"])
        name = r["lift_name"] or ""
        m = _NUM.search(name)
        a = _ASCN.search(normalize(name))
        ix.lifts.setdefault(r["station_id"], []).append(LiftDoc(
            lift_id=r["lift_id"], station_id=r["station_id"], station=r["station"], name=name,
            description=r["description"] or "", codes={c for c in r["codes"] if c},
            space_tokens={t for s in r["spaces"] if s for t in _tokens(s)} - GENERIC,
            number=m.group(1) if m else None, asc_n=a.group(1) if a else None))
    df: Counter = Counter()
    for st in ix.stations.values():
        st["tokens"] = {a: set(_tokens(a)) for a in st["aliases"]}
        for t in set().union(*st["tokens"].values()):
            df[t] += 1
    n = max(1, len(ix.stations))
    ix.idf = {t: math.log(1 + n / c) for t, c in df.items()}
    return ix


def _station_scores(ix: Index, toks: set[str]) -> list[tuple[float, str, str]]:
    out = []
    for sid, st in ix.stations.items():
        best = (0.0, "")
        for alias, at in st["tokens"].items():
            if not at:
                continue
            hit = sum(ix.idf.get(t, 1) for t in at & toks)
            tot = sum(ix.idf.get(t, 1) for t in at)
            score = hit / tot if tot else 0.0
            if score > best[0]:
                best = (score, alias)
        if best[0] > 0:
            out.append((round(best[0], 3), sid, best[1]))
    return sorted(out, key=lambda x: (-x[0], ix.stations[x[1]]["name"]))


def _codes_in(text: str, station_codes: set[str]) -> set[str]:
    n = normalize(text)
    found = set()
    for a, b in _PAIR.findall(n):
        found |= {a, b}
    for a in _SINGLE.findall(n):
        found.add(a)
    return {c for c in found if c in station_codes}


def reported_state(text: str) -> str:
    n = " " + normalize(text) + " "
    if any(w in n for w in UP):
        return "AVAILABLE"
    if any(w in n for w in DOWN):
        return "UNAVAILABLE"
    return "UNAVAILABLE"  # a report about a lift is assumed to be an outage unless it says otherwise


def resolve(ix: Index, text: str, max_candidates: int = 4, restrict_stations: list[str] | None = None) -> dict:
    """``restrict_stations``: the station is already known (e.g. the IDFM stop area of a feed message)."""
    text = (text or "")[:1000]
    toks = set(_tokens(text))
    if restrict_stations is not None:
        stations = [(1.0, sid, "IDFM stop area of the message") for sid in restrict_stations if sid in ix.stations]
    else:
        stations = _station_scores(ix, toks)
    if not stations or stations[0][0] < 0.5:
        return {"status": "NOT_FOUND", "text": text, "station_candidates": [
                    {"station_id": s, "name": ix.stations[s]["name"], "score": sc} for sc, s, _ in stations[:3]],
                "lift_candidates": [], "question": "Which station is it? No station name in the report matches the graph.",
                "reported_state": reported_state(text)}
    top = stations[0][0]
    close = [s for s in stations if s[0] >= top - 0.15 and s[0] >= 0.5][:3]
    nums = set(_NUM.findall(normalize(text)))
    ascs = set(_ASCN.findall(normalize(text)))
    cands = []
    for sc, sid, alias in close:
        lifts = ix.lifts.get(sid, [])
        station_codes = set().union(*(l.codes for l in lifts)) if lifts else set()
        codes = _codes_in(text, station_codes)
        for l in lifts:
            score, ev = sc * 2, [f"station “{ix.stations[sid]['name']}” matched via “{alias}”"]
            if codes:
                inter = codes & l.codes
                if inter:
                    score += 3 * len(inter) / len(codes | l.codes) + 1
                    ev.append(f"platform(s) {', '.join(sorted(c.upper() for c in inter))} — SERVES edge in the graph")
                elif l.codes:
                    score -= 1
            sp = (toks - GENERIC) & l.space_tokens
            if sp:
                score += 1.5 * len(sp)
                ev.append(f"space words {', '.join(sorted(sp))} — SERVES edge in the graph")
            if l.number and l.number in nums:
                score += 4
                ev.append(f"equipment number {l.number}")
            if l.asc_n and l.asc_n in ascs:
                score += 3
                ev.append(f"lift label ASC{l.asc_n}")
            cands.append({"lift_id": l.lift_id, "lift_name": l.name, "description": l.description,
                          "station_id": sid, "station_name": l.station, "score": round(score, 3), "evidence": ev})
    cands.sort(key=lambda c: (-c["score"], c["lift_name"], c["lift_id"]))
    cands = cands[:max_candidates]
    status, question = "AMBIGUOUS", None
    if not cands:
        question = f"The graph lists no lift at {ix.stations[close[0][1]]['name']}."
        status = "NOT_FOUND"
    elif len(cands) == 1 or (cands[0]["score"] - cands[1]["score"] >= 1.0 and len(cands[0]["evidence"]) >= 2):
        status = "RESOLVED"
    elif len(close) > 1 and cands[0]["station_id"] != cands[1]["station_id"]:
        question = "Several stations match — which one?"
    else:
        question = "Several lifts match — which platform or exit does it serve?"
    return {"status": status, "text": text, "reported_state": reported_state(text),
            "station_candidates": [{"station_id": s, "name": ix.stations[s]["name"], "score": sc, "matched_alias": a}
                                   for sc, s, a in close],
            "lift_candidates": cands, "question": question,
            "method": "Deterministic retrieval over Relate: station names + linked IDFM zone names, and the platforms "
                      "and spaces each lift SERVES. No language model is involved."}
