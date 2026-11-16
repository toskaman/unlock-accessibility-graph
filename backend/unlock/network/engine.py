"""Network-scale step-free journeys (pure computation over facts read from Relate).

A *journey* is an ordered pair of stations (A, B) such that a wheelchair user can board
at A and alight at B, possibly changing at intermediate stations, using only platforms
that are boardable (GTFS / IDFM) and *usable* in the chosen view:

* ``OPEN``   — no reported outage removes its step-free access;
* ``DOUBT``  — a reported lift outage concerns it and UNLOCK cannot tell whether another
               lift still serves it (the feed carries no redundancy information);
* ``CLOSED`` — UNLOCK's station topology (SNCF NeTEx + SERVES graph) shows that no
               platform of the station keeps a confirmed step-free route to the street.

``confirmed`` journeys use OPEN platforms only; ``possible`` journeys may use DOUBT ones.
Changes between lines happen at a station, from one usable platform to another (GTFS
parent_station); staying on the same platform between two patterns is not assumed.

Reachability is computed exactly with a strongly-connected-component condensation and
station bitsets — deterministic, independent of iteration order.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Iterable, Mapping

OPEN, DOUBT, CLOSED = "OPEN", "DOUBT", "CLOSED"
_RANK = {OPEN: 0, DOUBT: 1, CLOSED: 2}


def worst(a: str, b: str) -> str:
    return a if _RANK[a] >= _RANK[b] else b


@dataclass
class Network:
    stations: dict[str, dict]
    platforms: dict[str, dict]                       # boardable platforms only
    legs: list[tuple[str, str, str]]                 # (from platform, to platform, line)
    lines: dict[str, dict]
    station_platforms: dict[str, list[str]] = field(default_factory=dict)
    out_legs: dict[str, list[tuple[str, str]]] = field(default_factory=dict)

    def __post_init__(self):
        sp = defaultdict(list)
        for pid, p in self.platforms.items():
            sp[p["station_id"]].append(pid)
        self.station_platforms = {k: sorted(v) for k, v in sp.items()}
        ol = defaultdict(list)
        for a, b, line in self.legs:
            ol[a].append((b, line))
        self.out_legs = {k: sorted(v) for k, v in ol.items()}
        self.station_index = {s: i for i, s in enumerate(sorted(self.station_platforms))}


def reach_counts(net: Network, usable: set[str], into: dict[str, int] | None = None) -> tuple[int, dict[str, int]]:
    """Return (ordered station pairs reachable, per-origin count) using only ``usable`` platforms.
    If ``into`` is a dict, it is filled with the number of origins reaching each station."""
    # nodes: platforms (str) and station hubs ("#"+id)
    adj: dict[str, list[str]] = defaultdict(list)
    hubs = []
    for st, pids in net.station_platforms.items():
        u = [p for p in pids if p in usable]
        if not u:
            continue
        h = "#" + st
        hubs.append(h)
        for p in u:
            adj[h].append(p)
            adj[p].append(h)
    for p in usable:
        for q, _ in net.out_legs.get(p, ()):
            if q in usable:
                adj[p].append(q)
    nodes = sorted(adj.keys() | {q for v in adj.values() for q in v})
    # iterative Tarjan (components come out in reverse topological order)
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    onstack: set[str] = set()
    comp: dict[str, int] = {}
    stack: list[str] = []
    counter = ncomp = 0
    for root in nodes:
        if root in index:
            continue
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        onstack.add(root)
        call = [(root, iter(adj.get(root, ())))]
        while call:
            v, it = call[-1]
            advanced = False
            for w in it:
                if w not in index:
                    index[w] = low[w] = counter
                    counter += 1
                    stack.append(w)
                    onstack.add(w)
                    call.append((w, iter(adj.get(w, ()))))
                    advanced = True
                    break
                if w in onstack:
                    low[v] = min(low[v], index[w])
            if advanced:
                continue
            call.pop()
            if call:
                u = call[-1][0]
                low[u] = min(low[u], low[v])
            if low[v] == index[v]:
                while True:
                    w = stack.pop()
                    onstack.discard(w)
                    comp[w] = ncomp
                    if w == v:
                        break
                ncomp += 1
    # Tarjan emits components in reverse topological order: successors get smaller ids
    bits = [0] * ncomp
    members: dict[int, list[str]] = defaultdict(list)
    for v, c in comp.items():
        members[c].append(v)
    sidx = net.station_index
    for c in range(ncomp):
        b = 0
        for v in members[c]:
            if v[0] == "#":
                b |= 1 << sidx[v[1:]]
        for v in members[c]:
            for w in adj.get(v, ()):
                cw = comp[w]
                if cw != c:
                    b |= bits[cw]
        bits[c] = b
    per = {}
    total = 0
    names = sorted(sidx, key=sidx.get) if into is not None else None
    for h in hubs:
        b = bits[comp[h]]
        n = bin(b).count("1") - 1
        per[h[1:]] = n
        total += n
        if into is not None:
            own = sidx[h[1:]]
            while b:
                low_bit = b & -b
                i = low_bit.bit_length() - 1
                if i != own:
                    into[names[i]] = into.get(names[i], 0) + 1
                b ^= low_bit
    return total, per


TRANSFER_PENALTY = 8  # one boarding "costs" as much as riding 8 stops


def journey(net: Network, usable: set[str], a: str, b: str, hops: Mapping[tuple[str, str], int] | None = None) -> list[dict] | None:
    """Least-cost step-free journey A -> B: cost = stops ridden + TRANSFER_PENALTY per boarding (Dijkstra,
    ties broken by id). Legs are {board, alight, line, from, to}."""
    import heapq
    if a == b:
        return []
    start = [p for p in net.station_platforms.get(a, []) if p in usable]
    goal = {p for p in net.station_platforms.get(b, []) if p in usable}
    if not start or not goal:
        return None
    hops = hops or {}
    dist: dict[str, int] = {}
    prev: dict[str, tuple[str, str, str] | None] = {}
    heap = [(0, p, "") for p in start]
    for p in start:
        dist[p] = 0
        prev[p] = None
    heapq.heapify(heap)
    found = None
    while heap:
        d, p, _ = heapq.heappop(heap)
        if d > dist.get(p, 1 << 60):
            continue
        if p in goal and prev[p] is not None:
            found = p
            break
        for q, line in net.out_legs.get(p, ()):
            if q not in usable:
                continue
            nd = d + TRANSFER_PENALTY + hops.get((p, q), 1)
            st = net.platforms[q]["station_id"]
            for r in [q] + [x for x in net.station_platforms[st] if x in usable and x != q]:
                if nd < dist.get(r, 1 << 60):
                    dist[r] = nd
                    prev[r] = (p, line, q)
                    heapq.heappush(heap, (nd, r, r))
    if not found:
        return None
    legs = []
    r = found
    while prev[r] is not None:
        p, line, q = prev[r]
        legs.append({"board": p, "alight": q, "line": line,
                     "from": net.platforms[p]["station_id"], "to": net.platforms[q]["station_id"]})
        r = p
    return list(reversed(legs))


def reach_set(net: Network, usable: set[str], origin: str) -> set[str]:
    """Stations reachable step-free from ``origin`` (origin excluded) — same rules as journey()."""
    start = [p for p in net.station_platforms.get(origin, []) if p in usable]
    seen, out = set(start), set()
    dq = deque(start)
    while dq:
        p = dq.popleft()
        for q, _ in net.out_legs.get(p, ()):
            if q not in usable:
                continue
            st = net.platforms[q]["station_id"]
            out.add(st)
            for r in net.station_platforms[st]:
                if r in usable and r not in seen:
                    seen.add(r)
                    dq.append(r)
    out.discard(origin)
    return out


def usable_sets(states: Mapping[str, str], platforms: Iterable[str]) -> tuple[set[str], set[str]]:
    conf = {p for p in platforms if states.get(p, OPEN) == OPEN}
    poss = {p for p in platforms if states.get(p, OPEN) in (OPEN, DOUBT)}
    return conf, poss
