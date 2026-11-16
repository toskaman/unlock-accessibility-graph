"""Network reachability engine: exact counts vs brute force, journey search, platform placement."""
import random
from collections import deque

from region_fixture import line_reports, network
from unlock.network import engine as E
from unlock.network.load_net import network_rows
from unlock.network.outages import Placer, lift_key, parse_line_reports


def _net(doc):
    rows = network_rows(doc)
    pts = {}
    for p in doc["platforms"]:
        if p["boardable"]:
            for l in p["lines"]:
                pts[f"{p['id']}|{l}"] = {**p, "platform_id": p["id"], "line": l}
    legs = [(f"{l['a']}|{l['line']}", f"{l['b']}|{l['line']}", l["line"]) for l in rows["legs"]]
    return E.Network(stations={s["id"]: s for s in doc["stations"]}, platforms=pts, legs=legs,
                     lines={l["id"]: l for l in doc["lines"]})


def _brute(net, usable):
    tot = 0
    for st, ps in net.station_platforms.items():
        u = [p for p in ps if p in usable]
        if not u:
            continue
        seen, dq, sts = set(u), deque(u), {st}
        while dq:
            p = dq.popleft()
            for q, _ in net.out_legs.get(p, ()):
                if q in usable:
                    sts.add(net.platforms[q]["station_id"])
                    for r in [x for x in net.station_platforms[net.platforms[q]["station_id"]] if x in usable]:
                        if r not in seen:
                            seen.add(r)
                            dq.append(r)
        tot += len(sts) - 1
    return tot


def test_published_journeys_count():
    net = _net(network())
    total, per = E.reach_counts(net, set(net.platforms))
    assert total == 12            # every ordered pair among the 4 stations with a boardable platform
    assert "Z5" not in per        # Delta's tram stop is not boardable


def test_reach_counts_matches_brute_force_on_random_subsets():
    net = _net(network())
    rnd = random.Random(7)
    pts = sorted(net.platforms)
    for _ in range(40):
        sub = set(rnd.sample(pts, rnd.randint(0, len(pts))))
        assert E.reach_counts(net, sub)[0] == _brute(net, sub)


def test_directional_quay_cuts_one_direction_only():
    net = _net(network())
    usable = set(net.platforms) - {"M:Z3a|M1"}
    total, per = E.reach_counts(net, usable)
    assert total == 9 and per["Z3"] == 2   # Beta can no longer reach Gamma; Gamma still reaches Beta
    assert E.journey(net, usable, "Z1", "Z4") is None
    back = E.journey(net, usable, "Z4", "Z2")
    assert [l["line"] for l in back] == ["M1", "R1"]


def test_ride_through_a_station_does_not_need_its_platform():
    net = _net(network())
    usable = set(net.platforms) - {"R:Z1|R1"}
    legs = E.journey(net, usable, "Z2", "Z3")
    assert legs and legs[0]["from"] == "Z2" and legs[0]["to"] == "Z3"


def test_parse_groups_messages_by_lift_and_keeps_oldest_report():
    out = {o["id"]: o for o in parse_line_reports(line_reports())}
    assert set(out) == {"RATP:501", "GC:77"}           # the Travaux message is not a lift outage
    r = out["RATP:501"]
    assert r["messages"] == 2 and r["first_reported"] == "2026-08-01T08:00:00" and r["lines"] == ["M1"]
    assert lift_key("GARES_CONNEXIONS_elevator_1090_2026", "x") == ("SNCF_GC", "GC:1090")
    assert lift_key(None, "abc") == ("UNKNOWN", "MSG:abc")


def test_placement_direction_and_rail():
    pl = Placer(network())
    out = {o["id"]: o for o in parse_line_reports(line_reports())}
    a = pl.place(out["RATP:501"])
    assert [(x["platform_id"], x["derivation"]) for x in a["affects"]] == [("M:Z3a", "DIRECTION_MATCH")]
    b = pl.place(out["GC:77"])
    assert [(x["platform_id"], x["derivation"]) for x in b["affects"]] == [("R:Z1", "RAIL_STATION")]


def test_worst_and_usable_sets():
    assert E.worst(E.OPEN, E.DOUBT) == E.DOUBT and E.worst(E.CLOSED, E.DOUBT) == E.CLOSED
    conf, poss = E.usable_sets({"a": E.DOUBT, "b": E.CLOSED}, ["a", "b", "c"])
    assert conf == {"c"} and poss == {"a", "c"}
