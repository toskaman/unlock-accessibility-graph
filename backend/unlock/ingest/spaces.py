"""Derive an intra-station *space graph* from lift location text.

The SNCF NeTEx file says *where* each lift is in free text, e.g.
``"Voie 1 / souterrain"`` or ``"Cour du Havre / passerelle supérieure"``.
A lift with a two-sided description connects two spaces. This module turns
that text into graph facts and labels every fact with how it was derived:

=====================  =======================================================
derivation             meaning
=====================  =======================================================
VOIE_TOKEN             side names a track ("Voie 2", "Voies C et D") that
                       exactly matches a quay of the same station
QUAI_NUMBER            side names "Quai N" and the station has a "Voie N"
                       quay (weaker: quay and track numbering usually agree)
NAME_VOIE_TOKEN        description empty; track found in the lift *name*
NAMED_SPACE            side names a non-platform space ("souterrain", "hall");
                       identical normalised names in one station are merged
UNSPECIFIED_END        description gives only one side; the other end is a
                       per-lift placeholder that never connects to anything
=====================  =======================================================

Nothing here invents physical topology: a placeholder end can never create a
path between two anchors, and unresolved text is kept as UNRESOLVED.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

_MOJIBAKE = {"à¨": "è", "à©": "é", "à´": "ô", "à§": "ç", "à®": "î", "à¢": "â", "à«": "ë", "à\xa0": "à"}

EXIT_WORDS = (
    "hall", "parvis", "rue", "avenue", "boulevard", "sortie", "place", "cour ", "cour du", "cour de",
    "ville", "esplanade", "gare routiere", "depose minute", "bureau de vente", "parking", "dalle",
    "niveau rue", "exterieur", "centre commercial", "entree", "bv", "acces ",
)
INTERCHANGE_WORDS = ("metro", "ratp", "rer et metro")
CONNECTOR_WORDS = (
    "souterrain", "souterrrain", "passerelle", "mezzanine", "salle d'echange", "niv ", "niv+", "niv-",
    "niveau", "terrasse", "galerie", "couloir", "deck", "plateforme", "gare souterraine", "salle d'attente",
    "salle des pas perdus",
)
PRIVATE_WORDS = ("multiburo", "accueil", "salon", "annexe", "point groupe", "local psh", "atten")
NOT_EXIT_ACCESS = ("acces quais", "acces aux trains", "acces voies")

_CODE = r"(?:\d{1,2}(?:\s?(?:bis|b|l|m))?|[a-z]{1,2}(?:\s?bis)?)(?![a-z0-9])"
_VOIE_RE = re.compile(rf"\bvoies?\s+({_CODE}(?:\s*(?:,|et|&|-|a)\s*{_CODE})*)")
_RANGE_RE = re.compile(r"\bvoies?\s+(\d{1,2})\s+a\s+(\d{1,2})\b")
_QUAI_RE = re.compile(r"\bquai\s+(\d{1,2}|[a-h])\b")
_V_RE = re.compile(r"\bv(\d{1,2})\b")


def normalize(text: str | None) -> str:
    if not text:
        return ""
    for bad, good in _MOJIBAKE.items():
        text = text.replace(bad, good)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = text.replace("’", "'")
    return re.sub(r"\s+", " ", text).strip()


def quay_code(quay_name: str | None) -> str | None:
    """'Voie 1B' -> '1b'; 'Voie U' -> 'u'. Only names of the form 'Voie X'."""
    n = normalize(quay_name)
    m = re.fullmatch(r"voie\s+([0-9a-z]+)", n)
    return m.group(1) if m else None


def _canon(code: str, station_codes: set[str]) -> str:
    c = code.replace(" ", "")
    if c.endswith("bis"):
        b = c[:-3] + "b"
        if c not in station_codes and b in station_codes:
            return b
    return c


def extract_codes(side: str, station_codes: set[str]) -> tuple[set[str], set[str], str | None]:
    """Return (matched_codes, unmatched_tokens, derivation) for one side of a description."""
    found: list[str] = []
    derivation = None
    for a, b in _RANGE_RE.findall(side):
        found += [str(i) for i in range(int(a), int(b) + 1)]
    for grp in _VOIE_RE.findall(side):
        found += [t for t in re.split(r"\s*(?:,|\bet\b|&|-|\ba\b)\s*", grp) if t]
    found += _V_RE.findall(side)
    if found:
        derivation = "VOIE_TOKEN"
    else:
        q = _QUAI_RE.findall(side)
        if q:
            found, derivation = q, "QUAI_NUMBER"
    canon = {_canon(t, station_codes) for t in found}
    matched = {c for c in canon if c in station_codes}
    return matched, canon - matched, (derivation if matched else None)


def classify_named(side: str) -> str:
    s = f" {side} "
    if any(w in s for w in PRIVATE_WORDS):
        return "PRIVATE"
    if any(w in s for w in INTERCHANGE_WORDS):
        return "EXIT"
    if any(w in s for w in NOT_EXIT_ACCESS):
        return "CONNECTOR"
    if re.search(r"\bquai\b|\bvoies?\b|\bq\.? ?central\b|\brer [a-e]\b", s):
        return "UNRESOLVED_PLATFORM"
    if any(f" {w}" in s or s.strip().startswith(w.strip()) for w in EXIT_WORDS):
        return "EXIT"
    if any(w in s for w in CONNECTOR_WORDS):
        return "CONNECTOR"
    if re.search(r"\bquai\b|\bvoies?\b|\brer [a-e]\b", s):
        return "UNRESOLVED_PLATFORM"
    return "UNRESOLVED"


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:60] or "x"


@dataclass
class SpaceFact:
    id: str
    name: str
    role: str  # PLATFORM | EXIT | CONNECTOR | PRIVATE | UNRESOLVED | UNRESOLVED_PLATFORM | UNSPECIFIED
    quay_code: str | None = None


@dataclass
class ServesFact:
    lift_id: str
    space_id: str
    derivation: str
    side_text: str
    side_index: int


@dataclass
class LiftTopology:
    spaces: dict[str, SpaceFact] = field(default_factory=dict)
    serves: list[ServesFact] = field(default_factory=list)
    unmatched_tokens: list[tuple[str, str]] = field(default_factory=list)


def derive(station_uuid: str, quay_codes: set[str], lifts: list[tuple[str, str | None, str | None]],
           topo: LiftTopology | None = None) -> LiftTopology:
    """lifts: (lift_id, name, description). Returns spaces + SERVES facts for one station."""
    topo = topo or LiftTopology()

    def platform(code: str) -> str:
        sid = f"{station_uuid}:quay:{code}"
        topo.spaces.setdefault(sid, SpaceFact(sid, f"Voie {code.upper()}", "PLATFORM", code))
        return sid

    for lift_id, name, desc in lifts:
        text = normalize(desc)
        sides = [s.strip() for s in text.split("/") if s.strip()] if text else []
        used_name = False
        if not sides:
            n = normalize(name)
            codes, _, der = extract_codes(n, quay_codes)
            if codes:
                sides, used_name = [n], True
        resolved_any = False
        for idx, side in enumerate(sides[:2]):
            codes, unmatched, der = extract_codes(side, quay_codes)
            for tok in sorted(unmatched):
                topo.unmatched_tokens.append((lift_id, tok))
            if codes:
                for c in sorted(codes):
                    topo.serves.append(ServesFact(lift_id, platform(c), "NAME_VOIE_TOKEN" if used_name else der, side, idx))
                resolved_any = True
                continue
            role = classify_named(side)
            sid = f"{station_uuid}:space:{slug(side)}"
            topo.spaces.setdefault(sid, SpaceFact(sid, side, role))
            topo.serves.append(ServesFact(lift_id, sid, "NAMED_SPACE", side, idx))
            resolved_any = True
        if len(sides) < 2:
            sid = f"{station_uuid}:unspecified:{lift_id}"
            topo.spaces[sid] = SpaceFact(sid, "unspecified end", "UNSPECIFIED")
            topo.serves.append(ServesFact(lift_id, sid, "UNSPECIFIED_END", "", len(sides)))
            if not resolved_any:
                sid2 = f"{station_uuid}:unspecified:{lift_id}:b"
                topo.spaces[sid2] = SpaceFact(sid2, "unspecified end", "UNSPECIFIED")
                topo.serves.append(ServesFact(lift_id, sid2, "UNSPECIFIED_END", "", 1))
    return topo
