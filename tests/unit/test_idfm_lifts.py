"""IDFM lift-status parsing and the RATP station lift graph (synthetic lifts on the synthetic region)."""
from region_fixture import network
from unlock.network.idfm_lifts import LiftPlacer, classify_side, point_states


def test_classify_side():
    assert classify_side("Ligne M4 direction Porte de Clignancourt") == ("PLATFORM", [("4", "porte de clignancourt")])
    assert classify_side("Métro L14 direction Saint-Denis - Pleyel")[1][0][0] == "14"
    assert classify_side("Ligne RER B direction Saint-Rémy-les-Chevreuse")[1][0][0] == "b"
    assert classify_side("Accès 1 avenue Max Dormoy")[0] == "ACCESS"
    assert classify_side("Salle d'échange")[0] == "SPACE"
    assert classify_side("")[0] == "EMPTY"


def test_placer_direction_on_metro():
    pl = LiftPlacer(network())
    pts, how = pl.points("Z3", "1", "gamma")
    assert pts == [("M:Z3a", "M1")] and how == "DIRECTION_MATCH"


def _lift(i, sides, zdc="Z3"):
    return {"id": i, "operator": "RATP", "zdc": zdc, "sides": sides}


ACC = {"kind": "ACCESS"}
HALL = {"kind": "SPACE", "space": "salle d'echange"}
QA = {"kind": "PLATFORM", "points": [{"platform_id": "M:Z3a", "line_id": "M1"}]}
QB = {"kind": "PLATFORM", "points": [{"platform_id": "M:Z3b", "line_id": "M1"}]}


def test_point_states_chain_and_redundancy():
    lifts = [_lift("L1", [ACC, HALL]), _lift("L2", [HALL, QA]), _lift("L4", [ACC, QB])]
    ok = {i: "AVAILABLE" for i in ("L1", "L2", "L4")}
    assert point_states(lifts, ok) == {"M:Z3a|M1": ("OPEN", "STATION_LIFT_GRAPH"), "M:Z3b|M1": ("OPEN", "STATION_LIFT_GRAPH")}
    s = point_states(lifts, {**ok, "L1": "UNAVAILABLE"})       # hall cut from the street: QA closed, QB via L4
    assert s["M:Z3a|M1"][0] == "CLOSED" and s["M:Z3b|M1"][0] == "OPEN"
    lifts.append(_lift("L3", [HALL, QB]))                       # a second way into the hall, through platform QB
    assert point_states(lifts, {**ok, "L3": "AVAILABLE", "L1": "UNAVAILABLE"})["M:Z3a|M1"][0] == "OPEN"
    s = point_states(lifts[:3], {**ok, "L1": "UNKNOWN"})
    assert s["M:Z3a|M1"][0] == "DOUBT"


def test_rail_point_with_one_lift_out_is_doubt_and_dangling_lifts_fall_back():
    rail = {"kind": "PLATFORM", "points": [{"platform_id": "R:Z3", "line_id": "R1"}]}
    lifts = [_lift("A", [ACC, rail]), _lift("B", [ACC, rail]), _lift("C", [QA])]   # C lists one side only
    s = point_states(lifts, {"A": "AVAILABLE", "B": "UNAVAILABLE", "C": "UNAVAILABLE"}, rail_lines={"R1"})
    assert s["R:Z3|R1"] == ("DOUBT", "SOME_RAIL_PLATFORMS_CUT")
    assert s["M:Z3a|M1"] == ("DOUBT", "LIFT_TOUCHES_PLATFORM")


def test_night_snapshot_turns_fresh_switch_offs_into_unknown(tmp_path):
    import json
    from region_fixture import idfm_lifts, network
    from unlock.network.idfm_lifts import night_window, normalize_file, paris_local
    from datetime import datetime, timezone
    assert paris_local(datetime(2026, 7, 1, 12, tzinfo=timezone.utc)).hour == 14          # CEST
    assert paris_local(datetime(2026, 11, 17, 12, tzinfo=timezone.utc)).hour == 13        # CET
    assert night_window("2026-11-17T12:00:00+00:00") is None
    raw = idfm_lifts()
    raw["fetched_at"] = "2026-11-17T00:30:00+00:00"                                         # 01:30 in Paris
    raw["records"][0]["liftstateupdate"] = "2026-11-17T01:05"                               # switched off at 01:05
    (tmp_path / "r.json").write_text(json.dumps(raw), encoding="utf-8")
    d = normalize_file(network(), raw=tmp_path / "r.json", out=tmp_path / "o.json")
    l = d["lifts"][0]
    assert l["status"] == "UNKNOWN" and l["status_note"] == "NIGHT_CLOSURE_SUSPECTED" and l["raw_status"] == "notavailable"
    assert d["counts"]["night_closure_suspected"] == 1
    raw["fetched_at"] = "2026-11-17T09:00:00+00:00"                                         # still out in the morning
    (tmp_path / "r.json").write_text(json.dumps(raw), encoding="utf-8")
    assert normalize_file(network(), raw=tmp_path / "r.json", out=tmp_path / "o.json")["lifts"][0]["status"] == "UNAVAILABLE"
