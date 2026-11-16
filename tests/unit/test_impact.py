"""Pure engine logic: three-valued states, classification, ranking."""
import random

from unlock.engine import impact as I
from unlock.engine.model import Accessibility as Acc, EquipmentStatus as E, LiftInfo, Pair, PairClass as C, Route

A, U, K = E.AVAILABLE, E.UNAVAILABLE, E.UNKNOWN


def pair(routes, a=Acc.ACCESSIBLE, b=Acc.ACCESSIBLE, pid="p", st="S"):
    return Pair(pid, st, "a", "b", "PLATFORM", "PLATFORM", a, b, [Route(tuple(sorted(r)), tuple(r)) for r in routes])


def test_unknown_is_neither_available_nor_unavailable():
    p = pair([["L1"]])
    r = I.classify(p, {"L1": K})
    assert r.cls == C.UNVERIFIED
    assert r.cls not in (C.CONFIRMED_ACCESSIBLE, C.CONFIRMED_BLOCKED)


def test_missing_status_defaults_to_unknown_not_available():
    assert I.route_state(Route(("L9",), ("a", "L9", "b")), {}) == K


def test_alternative_route_keeps_pair_reachable():
    p = pair([["L1", "L2"], ["L4", "L5"]])
    assert I.classify(p, {"L1": U, "L2": A, "L4": A, "L5": A}).cls == C.CONFIRMED_ACCESSIBLE


def test_all_routes_blocked_is_blocked():
    p = pair([["L1"], ["L4"]])
    r = I.classify(p, {"L1": U, "L4": U})
    assert r.cls == C.CONFIRMED_BLOCKED and r.blocking_lifts == ("L1", "L4")


def test_blocked_plus_unknown_is_unverified():
    p = pair([["L1"], ["L4"]])
    assert I.classify(p, {"L1": U, "L4": K}).cls == C.UNVERIFIED


def test_uncertainty_propagates_from_endpoint_assertion():
    p = pair([["L1"]], b=Acc.UNKNOWN)
    assert I.classify(p, {"L1": A}).cls == C.UNVERIFIED


def test_source_inaccessible_endpoint_blocks_regardless_of_lifts():
    p = pair([["L1"]], b=Acc.INACCESSIBLE)
    assert I.classify(p, {"L1": A}).cls == C.CONFIRMED_BLOCKED


def test_no_route_is_out_of_scope():
    assert I.classify(pair([]), {}).cls == C.OUT_OF_SCOPE


def test_freshness_policy():
    from datetime import datetime, timezone
    now = datetime(2026, 11, 16, 12, tzinfo=timezone.utc)
    assert I.freshness("2026-11-16T11:00:00+00:00", now)[0].value == "CURRENT"
    assert I.freshness("2026-11-16T00:00:00+00:00", now)[0].value == "AGING"
    assert I.freshness("2026-11-10T00:00:00+00:00", now)[0].value == "STALE"
    assert I.freshness(None, now)[0].value == "UNKNOWN"


def _world():
    pairs = [pair([["L1", "L2"]], pid="p1"), pair([["L2"]], pid="p2"), pair([["L3"]], pid="p3", st="T"),
             pair([["L4", "L5"]], pid="p4", st="T")]
    lifts = {l: LiftInfo(l, "T" if l in ("L3", "L4", "L5") else "S", l, None, A, "OK") for l in ["L1", "L2", "L3", "L4", "L5"]}
    state = {"L1": A, "L2": U, "L3": U, "L4": U, "L5": U}
    return pairs, lifts, state


def test_marginal_gain_and_series_lifts():
    pairs, lifts, state = _world()
    ranked = {c.lift_id: c for c in I.rank_interventions(pairs, lifts, state)}
    assert ranked["L2"].gain == 2      # p1 and p2
    assert ranked["L3"].gain == 1
    assert ranked["L4"].gain == 0 and ranked["L4"].still_blocked_by_others == ["L5"]
    plan = I.best_plan(pairs, lifts, state, budget=2)
    assert plan["gain"] == 3 and sorted(plan["lifts"]) == ["L2", "L3"]


def test_exact_plan_beats_greedy_when_series_pays_off():
    pairs = [pair([["L1", "L2"]], pid=f"q{i}", st="S") for i in range(3)] + [pair([["L3"]], pid="r", st="T")]
    lifts = {l: LiftInfo(l, "T" if l == "L3" else "S", l, None, A, "OK") for l in ["L1", "L2", "L3"]}
    state = {"L1": U, "L2": U, "L3": U}
    plan = I.best_plan(pairs, lifts, state, budget=2)
    assert plan["gain"] == 3 and sorted(plan["lifts"]) == ["L1", "L2"]
    assert plan["greedy"]["gain"] == 1   # greedy takes L3 first, then nothing pays alone


def test_determinism_and_order_invariance():
    pairs, lifts, state = _world()
    ref = [(c.lift_id, c.gain) for c in I.rank_interventions(pairs, lifts, state)]
    for seed in range(5):
        p2 = pairs[:]; random.Random(seed).shuffle(p2)
        l2 = dict(sorted(lifts.items(), key=lambda kv: random.Random(seed).random()))
        assert [(c.lift_id, c.gain) for c in I.rank_interventions(p2, l2, state)] == ref


def test_overrides_do_not_mutate_baseline():
    lifts = {"L1": LiftInfo("L1", "S", "L1", None, A, "OK")}
    s = I.effective_state(lifts, {"L1": U})
    assert s["L1"] == U and lifts["L1"].baseline == A
