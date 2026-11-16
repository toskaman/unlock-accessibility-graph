"""Parse the SNCF Gares & Connexions NeTEx accessibility file.

Only facts that are literally present in the file are extracted. Booleans in
NeTEx accessibility limitations are three-valued (true / false / unknown) and
are preserved as such — an absent element stays UNKNOWN, never ACCESSIBLE.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

NS = {"n": "http://www.netex.org.uk/netex"}
_LIMIT_FIELDS = (
    "WheelchairAccess", "StepFreeAccess", "EscalatorFreeAccess", "LiftFreeAccess",
    "AudibleSignalsAvailable", "VisualSignsAvailable", "TactileGuidanceAvailable",
)


def tri(value: str | None) -> str:
    """NeTEx limitation value -> ACCESSIBLE / INACCESSIBLE / UNKNOWN."""
    if value is None:
        return "UNKNOWN"
    v = value.strip().lower()
    if v == "true":
        return "ACCESSIBLE"
    if v == "false":
        return "INACCESSIBLE"
    return "UNKNOWN"  # 'unknown', 'partial' or anything unexpected


@dataclass
class Assessment:
    mobility_impaired_access: str
    limits: dict[str, str]


@dataclass
class Quay:
    id: str
    name: str | None
    public_code: str | None
    description: str | None
    lon: float | None
    lat: float | None
    assessment: Assessment | None


@dataclass
class Lift:
    id: str
    name: str | None
    description: str | None
    status_attr: str | None
    depth_mm: int | None
    max_load_kg: int | None
    width_mm: int | None
    lon: float | None
    lat: float | None


@dataclass
class StopPlace:
    id: str
    uuid: str
    insee: str
    name: str | None
    lon: float | None
    lat: float | None
    transport_mode: str | None
    stop_place_type: str | None
    assessment: Assessment | None
    quays: list[Quay] = field(default_factory=list)
    lifts: list[Lift] = field(default_factory=list)


def _t(e: ET.Element, path: str) -> str | None:
    x = e.find(path, NS)
    return x.text.strip() if x is not None and x.text is not None else None


def _f(e: ET.Element, path: str) -> float | None:
    v = _t(e, path)
    try:
        return float(v) if v is not None else None
    except ValueError:
        return None


def _i(e: ET.Element, path: str) -> int | None:
    v = _t(e, path)
    try:
        return int(float(v)) if v is not None else None
    except ValueError:
        return None


def _assessment(e: ET.Element) -> Assessment | None:
    a = e.find("n:AccessibilityAssessment", NS)
    if a is None:
        return None
    lim = a.find("n:limitations/n:AccessibilityLimitation", NS)
    limits = {k: tri(_t(lim, f"n:{k}")) if lim is not None else "UNKNOWN" for k in _LIMIT_FIELDS}
    return Assessment(tri(_t(a, "n:MobilityImpairedAccess")), limits)


def parse(path: Path) -> tuple[str | None, list[StopPlace]]:
    root = ET.parse(path).getroot()
    published = _t(root, "n:PublicationTimestamp")
    out: list[StopPlace] = []
    for sp in root.iter(f"{{{NS['n']}}}StopPlace"):
        sid = sp.get("id") or ""
        parts = sid.split(":")
        # id layout observed: FR:<INSEE>:LMO:<uuid>:LOC
        insee = parts[1] if len(parts) > 3 else ""
        uuid = parts[3] if len(parts) > 3 else sid
        place = StopPlace(
            id=sid, uuid=uuid, insee=insee, name=_t(sp, "n:Name"),
            lon=_f(sp, "n:Centroid/n:Location/n:Longitude"),
            lat=_f(sp, "n:Centroid/n:Location/n:Latitude"),
            transport_mode=_t(sp, "n:TransportMode"),
            stop_place_type=_t(sp, "n:StopPlaceType"),
            assessment=_assessment(sp),
        )
        for q in sp.findall("n:quays/n:Quay", NS):
            place.quays.append(Quay(
                id=q.get("id") or "", name=_t(q, "n:Name"), public_code=_t(q, "n:PublicCode"),
                description=_t(q, "n:Description"),
                lon=_f(q, "n:Centroid/n:Location/n:Longitude"),
                lat=_f(q, "n:Centroid/n:Location/n:Latitude"),
                assessment=_assessment(q),
            ))
        for ep in sp.findall(".//n:EquipmentPlace", NS):
            for le in ep.findall("n:placeEquipments/n:LiftEquipment", NS):
                place.lifts.append(Lift(
                    id=le.get("id") or "", name=_t(le, "n:Name"), description=_t(le, "n:Description"),
                    status_attr=le.get("status"), depth_mm=_i(le, "n:Depth"),
                    max_load_kg=_i(le, "n:MaximumLoad"), width_mm=_i(le, "n:Width"),
                    lon=_f(ep, "n:Centroid/n:Location/n:Longitude"),
                    lat=_f(ep, "n:Centroid/n:Location/n:Latitude"),
                ))
        out.append(place)
    return published, out
