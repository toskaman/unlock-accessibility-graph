"""Deterministic impact calculations (pure functions, no I/O).

Inputs are graph facts already retrieved from Relate (``Pair`` routes, endpoint
assertions, lift states). Same inputs -> same outputs, independent of the order
in which candidates are processed.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from itertools import combinations
from typing import Iterable, Mapping

from .model import (
    Accessibility, EquipmentStatus, Freshness, LiftInfo, Pair, PairClass, PairResult, Reason, Route,
)

A, U, K = EquipmentStatus.AVAILABLE, EquipmentStatus.UNAVAILABLE, EquipmentStatus.UNKNOWN
_ORDER = {A: 0, K: 1, U: 2}  # lower is better


def route_state(route: Route, state: Mapping[str, EquipmentStatus]) -> EquipmentStatus:
    """A route is AVAILABLE only if every lift on it is known AVAILABLE.

    Any UNAVAILABLE lift blocks it; otherwise any UNKNOWN lift makes it UNKNOWN.
    A lift missing from ``state`` is UNKNOWN — never assumed to work.
    """
    worst = A
    for lift in route.lifts:
        s = state.get(lift, K)
        if s == U:
            return U
        if s == K:
            worst = K
    return worst


def classify(pair: Pair, state: Mapping[str, EquipmentStatus]) -> PairResult:
    if not pair.routes:
        return PairResult(PairClass.OUT_OF_SCOPE, Reason.NO_MODELED_ROUTE, [])
    states = [route_state(r, state) for r in pair.routes]
    endpoints = (pair.a_assertion, pair.b_assertion)
    blocking = tuple(sorted({l for r in pair.routes for l in r.lifts if state.get(l, K) == U}))
    unknown = tuple(sorted({l for r in pair.routes for l in r.lifts if state.get(l, K) == K}))
    if Accessibility.INACCESSIBLE in endpoints:
        return PairResult(PairClass.CONFIRMED_BLOCKED, Reason.ENDPOINT_NOT_STEP_FREE, states, blocking, unknown)
    if A in states:
        if all(e in (Accessibility.ACCESSIBLE, Accessibility.NOT_APPLICABLE) for e in endpoints):
            return PairResult(PairClass.CONFIRMED_ACCESSIBLE, Reason.ROUTE_ALL_LIFTS_AVAILABLE, states, blocking, unknown)
        return PairResult(PairClass.UNVERIFIED, Reason.ENDPOINT_ASSERTION_UNKNOWN, states, blocking, unknown)
    if K in states:
        return PairResult(PairClass.UNVERIFIED, Reason.LIFT_STATUS_UNKNOWN, states, blocking, unknown)
    return PairResult(PairClass.CONFIRMED_BLOCKED, Reason.ALL_MODELED_ROUTES_BLOCKED, states, blocking, unknown)


def effective_state(lifts: Mapping[str, LiftInfo], overrides: Mapping[str, EquipmentStatus]) -> dict[str, EquipmentStatus]:
    """Baseline observations with scenario overrides laid on top (baseline untouched)."""
    s = {lid: li.baseline for lid, li in lifts.items()}
    s.update(overrides)
    return s


@dataclass
class Evaluation:
    results: dict[str, PairResult]
    counts: dict[str, int]

    def confirmed(self) -> set[str]:
        return {pid for pid, r in self.results.items() if r.cls == PairClass.CONFIRMED_ACCESSIBLE}


def evaluate(pairs: Iterable[Pair], state: Mapping[str, EquipmentStatus]) -> Evaluation:
    results = {p.id: classify(p, state) for p in pairs}
    c = Counter(r.cls.value for r in results.values())
    counts = {k.value: c.get(k.value, 0) for k in PairClass}
    counts["TOTAL"] = len(results)
    return Evaluation(results, counts)


def diff(before: Evaluation, after: Evaluation) -> dict[str, list[str]]:
    """Pairs whose class changed, grouped as 'FROM->TO' (sorted, deterministic)."""
    out: dict[str, list[str]] = {}
    for pid in sorted(before.results):
        b, a = before.results[pid].cls, after.results[pid].cls
        if b != a:
            out.setdefault(f"{b.value}->{a.value}", []).append(pid)
    return out


def freshness(observed_at: str | None, now: datetime | None = None) -> tuple[Freshness, float | None]:
    """Publisher refreshes hourly: <=2h CURRENT, <=24h AGING, otherwise STALE."""
    if not observed_at:
        return Freshness.UNKNOWN, None
    try:
        t = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except ValueError:
        return Freshness.UNKNOWN, None
    now = now or datetime.now(timezone.utc)
    hours = (now - t).total_seconds() / 3600
    if hours <= 2:
        return Freshness.CURRENT, hours
    if hours <= 24:
        return Freshness.AGING, hours
    return Freshness.STALE, hours


# --- interventions -----------------------------------------------------------

@dataclass
class Candidate:
    lift_id: str
    station_id: str
    current_state: EquipmentStatus
    gain: int                                  # Δ confirmed accessible pairs
    restored_pairs: list[str]                  # pairs that become CONFIRMED_ACCESSIBLE
    resolved_unverified: int                   # UNVERIFIED pairs that become decided
    pairs_depending: int                       # pairs with at least one route through this lift
    still_blocked_by_others: list[str] = field(default_factory=list)


def _local(pairs_by_station: Mapping[str, list[Pair]], station: str) -> list[Pair]:
    return pairs_by_station.get(station, [])


def rank_interventions(pairs: list[Pair], lifts: Mapping[str, LiftInfo],
                       state: Mapping[str, EquipmentStatus]) -> list[Candidate]:
    """Score restoring each non-available lift to AVAILABLE, one at a time.

    Gain(i) = |confirmed(S + i)| - |confirmed(S)| over the *same* pair set.
    Only pairs of the lift's own station can change (routes never leave a
    station), so evaluation is local — identical to a global recount.
    """
    by_station: dict[str, list[Pair]] = {}
    for p in pairs:
        by_station.setdefault(p.station_id, []).append(p)
    uses: dict[str, int] = Counter(l for p in pairs for l in {x for r in p.routes for x in r.lifts})
    out: list[Candidate] = []
    for lid in sorted(lifts):
        cur = state.get(lid, K)
        if cur == A or uses.get(lid, 0) == 0:
            continue
        local = _local(by_station, lifts[lid].station_id)
        before = evaluate(local, state)
        trial = dict(state); trial[lid] = A
        after = evaluate(local, trial)
        restored = sorted(after.confirmed() - before.confirmed())
        resolved = sum(1 for pid, r in before.results.items()
                       if r.cls == PairClass.UNVERIFIED and after.results[pid].cls != PairClass.UNVERIFIED)
        depending = {p.id for p in local if any(lid in rt.lifts for rt in p.routes)}
        others = sorted({l for pid in depending for l in after.results[pid].blocking_lifts
                         if after.results[pid].cls != PairClass.CONFIRMED_ACCESSIBLE and l != lid})
        out.append(Candidate(lid, lifts[lid].station_id, cur, len(after.confirmed()) - len(before.confirmed()),
                             restored, resolved, uses[lid], others))
    out.sort(key=lambda c: (-c.gain, -c.resolved_unverified, -c.pairs_depending, c.lift_id))
    return out


def best_plan(pairs: list[Pair], lifts: Mapping[str, LiftInfo], state: Mapping[str, EquipmentStatus],
              budget: int, max_station_candidates: int = 12) -> dict:
    """Exact best set of ``budget`` repairs (by Δ confirmed pairs).

    Routes never cross stations, so gains are additive *across* stations but
    not within one (lifts in series only pay off together). We enumerate subsets
    per station (capped) and combine stations with a small knapsack DP.
    Returns the plan plus the greedy plan for comparison.
    """
    by_station: dict[str, list[Pair]] = {}
    for p in pairs:
        by_station.setdefault(p.station_id, []).append(p)
    used = {l for p in pairs for r in p.routes for l in r.lifts}
    cand_by_station: dict[str, list[str]] = {}
    for lid in sorted(lifts):
        if state.get(lid, K) != A and lid in used:
            cand_by_station.setdefault(lifts[lid].station_id, []).append(lid)
    tables: dict[str, list[tuple[int, tuple[str, ...]]]] = {}
    exact = True
    for st, cands in sorted(cand_by_station.items()):
        if len(cands) > max_station_candidates:
            exact = False
            cands = cands[:max_station_candidates]
        local = by_station[st]
        base = len(evaluate(local, state).confirmed())
        row = [(0, ())]
        for k in range(1, min(budget, len(cands)) + 1):
            best = (-1, ())
            for combo in combinations(cands, k):
                trial = dict(state); trial.update({c: A for c in combo})
                g = len(evaluate(local, trial).confirmed()) - base
                if g > best[0]:
                    best = (g, combo)
            row.append(best)
        tables[st] = row
    # knapsack over stations: dp[b] = (gain, chosen)
    dp: list[tuple[int, tuple[str, ...]]] = [(0, ())] * (budget + 1)
    for st in sorted(tables):
        row = tables[st]
        new = list(dp)
        for b in range(budget + 1):
            for k in range(1, len(row)):
                if k <= b and row[k][0] > 0:
                    g = dp[b - k][0] + row[k][0]
                    if g > new[b][0]:
                        new[b] = (g, tuple(sorted(dp[b - k][1] + row[k][1])))
        dp = new
    gain, chosen = dp[budget]
    # greedy for comparison (marginal, recomputed after each pick)
    g_state, greedy, g_total = dict(state), [], 0
    for _ in range(budget):
        ranked = rank_interventions(pairs, lifts, g_state)
        if not ranked or ranked[0].gain <= 0:
            break
        top = ranked[0]
        greedy.append({"lift_id": top.lift_id, "marginal_gain": top.gain})
        g_total += top.gain
        g_state[top.lift_id] = A
    return {"budget": budget, "exact": exact, "gain": gain, "lifts": list(chosen),
            "greedy": {"gain": g_total, "steps": greedy}}
