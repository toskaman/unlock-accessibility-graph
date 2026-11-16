"""Domain vocabulary for the impact engine.

Two dimensions are kept apart on purpose:

* **Accessibility** — a *physical* assertion published by a source about a place
  (ACCESSIBLE / INACCESSIBLE / UNKNOWN / NOT_APPLICABLE).
* **EquipmentStatus** — the *operational* state of a lift
  (AVAILABLE / UNAVAILABLE / UNKNOWN).

Freshness is a third, separate property of a status snapshot and never changes
a classification by itself (see docs/METHODOLOGY.md, "Freshness policy").
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Accessibility(str, Enum):
    ACCESSIBLE = "ACCESSIBLE"
    INACCESSIBLE = "INACCESSIBLE"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class EquipmentStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


class Freshness(str, Enum):
    CURRENT = "CURRENT"
    AGING = "AGING"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class PairClass(str, Enum):
    CONFIRMED_ACCESSIBLE = "CONFIRMED_ACCESSIBLE"
    CONFIRMED_BLOCKED = "CONFIRMED_BLOCKED"
    UNVERIFIED = "UNVERIFIED"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


class Reason(str, Enum):
    ROUTE_ALL_LIFTS_AVAILABLE = "ROUTE_ALL_LIFTS_AVAILABLE"
    ENDPOINT_NOT_STEP_FREE = "ENDPOINT_NOT_STEP_FREE"          # source asserts INACCESSIBLE
    ENDPOINT_ASSERTION_UNKNOWN = "ENDPOINT_ASSERTION_UNKNOWN"  # route ok but endpoint unknown
    LIFT_STATUS_UNKNOWN = "LIFT_STATUS_UNKNOWN"                # best route depends on unknown lift
    ALL_MODELED_ROUTES_BLOCKED = "ALL_MODELED_ROUTES_BLOCKED"  # every modeled route needs an unavailable lift
    NO_MODELED_ROUTE = "NO_MODELED_ROUTE"                      # topology not represented


ANCHOR_ROLES = ("PLATFORM", "UNRESOLVED_PLATFORM", "EXIT")


@dataclass(frozen=True)
class Route:
    lifts: tuple[str, ...]          # sorted, minimal lift set
    nodes: tuple[str, ...]          # representative node-id sequence (Space, Lift, Space, ...)


@dataclass
class Pair:
    id: str
    station_id: str
    a: str
    b: str
    a_role: str
    b_role: str
    a_assertion: Accessibility
    b_assertion: Accessibility
    routes: list[Route] = field(default_factory=list)

    @property
    def kind(self) -> str:
        roles = {self.a_role, self.b_role}
        return "PLATFORM_EXIT" if "EXIT" in roles else "PLATFORM_PLATFORM"


@dataclass
class LiftInfo:
    id: str
    station_id: str
    name: str | None
    description: str | None
    baseline: EquipmentStatus
    raw_state: str | None


@dataclass
class PairResult:
    cls: PairClass
    reason: Reason
    route_states: list[EquipmentStatus]
    blocking_lifts: tuple[str, ...] = ()
    unknown_lifts: tuple[str, ...] = ()
