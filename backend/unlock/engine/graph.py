"""Graph-backed retrieval. Every function here runs Cypher against Relate.

The impact engine never reads a CSV or a JSON file: the dependency structure
(which lifts each modeled route needs), the endpoint assertions and the status
observations all come from the store through these queries.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from ..db import GraphStore
from .model import ANCHOR_ROLES, Accessibility, EquipmentStatus, LiftInfo, Pair, Route

MAX_LIFTS_PER_ROUTE = 5

# All acyclic routes between pairs of anchor spaces of the same station.
# (Space)<-[:SERVES]-(Lift)-[:SERVES]->(Space) alternates, so a route of n lifts
# has 2n relationships. ACYCLIC forbids revisiting a node.
Q_ROUTES = f"""
MATCH (st:Station)-[:HAS_SPACE]->(a:Space)
WHERE a.role IN $roles AND ($stations IS NULL OR st.id IN $stations)
MATCH (st)-[:HAS_SPACE]->(b:Space)
WHERE b.role IN $roles AND a.id < b.id AND NOT (a.role = 'EXIT' AND b.role = 'EXIT')
OPTIONAL MATCH p = ACYCLIC (a)-[:SERVES]-{{2,{2 * MAX_LIFTS_PER_ROUTE}}}(b)
RETURN st.id AS station, a.id AS a, a.role AS a_role, b.id AS b, b.role AS b_role,
       [n IN nodes(p) | n.id] AS nodes,
       [n IN nodes(p) WHERE n:Lift | n.id] AS lifts
"""

Q_ENDPOINT_ASSERTIONS = """
MATCH (sp:Space) WHERE sp.role IN $roles AND ($stations IS NULL OR EXISTS { MATCH (s:Station)-[:HAS_SPACE]->(sp) WHERE s.id IN $stations })
OPTIONAL MATCH (sp)-[:IS_PLATFORM_OF]->(q:Quay)<-[:ABOUT]-(a:AccessibilityAssertion {dimension: 'StepFreeAccess'})
RETURN sp.id AS space, sp.role AS role, collect(a.value) AS values
"""

Q_LIFT_STATES = """
MATCH (s:Station)-[:HAS_LIFT]->(l:Lift)
OPTIONAL MATCH (l)-[:HAS_STATUS]->(o:StatusSnapshot {snapshot_id: $snapshot})
RETURN l.id AS id, s.id AS station, l.name AS name, l.description AS description,
       o.state AS state, o.raw_state AS raw_state
ORDER BY id
"""


def _assertion(role: str, values: list[str]) -> Accessibility:
    if role == "EXIT":
        return Accessibility.NOT_APPLICABLE
    if not values:
        return Accessibility.UNKNOWN
    vals = set(values)
    if vals == {"ACCESSIBLE"}:
        return Accessibility.ACCESSIBLE
    if "INACCESSIBLE" in vals:
        return Accessibility.INACCESSIBLE
    return Accessibility.UNKNOWN


def minimal_routes(raw: list[tuple[tuple[str, ...], tuple[str, ...]]]) -> list[Route]:
    """Keep one representative route per *minimal* lift set.

    A route whose lift set is a strict superset of another route's set can
    never be available when the smaller one is not, so it never changes a
    classification; dropping it keeps evidence readable. Deterministic order.
    """
    best: dict[tuple[str, ...], tuple[str, ...]] = {}
    for lifts, nodes in raw:
        key = tuple(sorted(set(lifts)))
        if key not in best or (len(nodes), nodes) < (len(best[key]), best[key]):
            best[key] = nodes
    keys = sorted(best, key=lambda k: (len(k), k))
    minimal = [k for k in keys if not any(set(o) < set(k) for o in keys)]
    return [Route(k, best[k]) for k in minimal]


def load_pairs(db: GraphStore, stations: list[str] | None = None) -> list[Pair]:
    params: dict[str, Any] = {"roles": list(ANCHOR_ROLES), "stations": stations}
    assertions = {r["space"]: _assertion(r["role"], r["values"]) for r in db.query(Q_ENDPOINT_ASSERTIONS, params)}
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    raw: dict[tuple[str, str], list] = defaultdict(list)
    for r in db.query(Q_ROUTES, params):
        key = (r["a"], r["b"])
        grouped.setdefault(key, r)
        if r["nodes"]:
            raw[key].append((tuple(r["lifts"]), tuple(r["nodes"])))
    pairs = []
    for key in sorted(grouped):
        r = grouped[key]
        pairs.append(Pair(
            id=f"{r['a']}|{r['b']}", station_id=r["station"], a=r["a"], b=r["b"],
            a_role=r["a_role"], b_role=r["b_role"],
            a_assertion=assertions.get(r["a"], Accessibility.UNKNOWN),
            b_assertion=assertions.get(r["b"], Accessibility.UNKNOWN),
            routes=minimal_routes(raw.get(key, [])),
        ))
    return pairs


def load_lifts(db: GraphStore, snapshot_id: str) -> dict[str, LiftInfo]:
    out = {}
    for r in db.query(Q_LIFT_STATES, {"snapshot": snapshot_id}):
        state = r["state"]
        out[r["id"]] = LiftInfo(
            id=r["id"], station_id=r["station"], name=r["name"], description=r["description"],
            baseline=EquipmentStatus(state) if state else EquipmentStatus.UNKNOWN, raw_state=r["raw_state"],
        )
    return out


def latest_snapshot(db: GraphStore) -> dict[str, Any] | None:
    rows = db.query("""MATCH (o:StatusSnapshot)
        RETURN o.snapshot_id AS id, max(o.observed_at) AS observed_at, count(*) AS n
        ORDER BY observed_at DESC, id DESC LIMIT 1""")
    return rows[0] if rows else None


# --- evidence & explanation ------------------------------------------------

Q_ROUTE_PATH = """
MATCH p = ACYCLIC (a:Space {id: $a})-[:SERVES]-{2,10}(b:Space {id: $b})
WHERE [n IN nodes(p) | n.id] = $nodes
RETURN p LIMIT 1
"""

Q_LIFT_EVIDENCE = """
MATCH (s:Station)-[:HAS_LIFT]->(l:Lift {id: $id})
OPTIONAL MATCH (l)-[e:SERVES]->(sp:Space)
OPTIONAL MATCH (l)-[:HAS_STATUS]->(o:StatusSnapshot {snapshot_id: $snapshot})-[:REPORTED_IN]->(ds:Dataset)
OPTIONAL MATCH (l)-[:DESCRIBED_IN]->(dn:Dataset)
RETURN l {.*} AS lift, s {.id, .name} AS station,
       collect(DISTINCT {space_id: sp.id, space_name: sp.name, role: sp.role, derivation: e.derivation,
                         side_text: e.side_text}) AS serves,
       o {.*} AS status, ds {.key, .title, .publisher, .licence, .sha256, .retrieved_at, .publisher_modified, .url} AS status_dataset,
       dn {.key, .title, .publisher, .licence, .sha256, .retrieved_at, .published, .url} AS description_dataset
"""

Q_SPACE_EVIDENCE = """
MATCH (s:Station)-[:HAS_SPACE]->(sp:Space {id: $id})
OPTIONAL MATCH (sp)-[:IS_PLATFORM_OF]->(q:Quay)<-[:ABOUT]-(a:AccessibilityAssertion)-[:SUPPORTED_BY]->(d:Dataset)
RETURN sp {.*} AS space, s {.id, .name} AS station, q {.id, .name, .code} AS quay,
       a {.id, .dimension, .value, .source_field, .wheelchair} AS assertion,
       d {.key, .title, .publisher, .licence, .sha256} AS dataset
"""


def route_path(db: GraphStore, nodes: tuple[str, ...]) -> dict[str, Any] | None:
    rows = db.query(Q_ROUTE_PATH, {"a": nodes[0], "b": nodes[-1], "nodes": list(nodes)})
    return rows[0]["p"] if rows else None


def lift_evidence(db: GraphStore, lift_id: str, snapshot_id: str) -> dict[str, Any] | None:
    rows = db.query(Q_LIFT_EVIDENCE, {"id": lift_id, "snapshot": snapshot_id})
    return rows[0] if rows else None


def space_evidence(db: GraphStore, space_id: str) -> dict[str, Any] | None:
    rows = db.query(Q_SPACE_EVIDENCE, {"id": space_id})
    return rows[0] if rows else None
