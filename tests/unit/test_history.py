"""Lift-status history: spells, chronic share, idempotent appends (synthetic observations)."""
from unlock import history as H


def _o(t, na):
    return {"observed_at": t, "sha256": t, "lifts": 3, "not_available": na}


OBS = [_o("2026-11-17T10:00:00+00:00", {"A": "UNAVAILABLE"}),
       _o("2026-11-17T18:00:00+00:00", {"A": "UNAVAILABLE", "B": "UNKNOWN"}),
       _o("2026-11-18T10:00:00+00:00", {"B": "UNAVAILABLE"}),
       _o("2026-11-18T18:00:00+00:00", {"A": "UNAVAILABLE"})]


def test_spells_and_share():
    sp = H.outage_spells(OBS)
    assert [(s["start"][:13], (s["end"] or "")[:13], s["still_out"]) for s in sp["A"]] == [
        ("2026-11-17T10", "2026-11-18T10", False), ("2026-11-18T18", "", True)]
    assert sp["B"][0]["states"] == ["UNAVAILABLE", "UNKNOWN"]
    assert H.share_out(OBS) == {"A": 0.75, "B": 0.25}


def test_appends_are_idempotent(tmp_path):
    p = tmp_path / "s.json"
    H.append_sncf(OBS[0], p)
    H.append_sncf(OBS[0], p)
    assert len(H.append_sncf(OBS[1], p)["observations"]) == 2
    row = {"region": "idf", "sncf_observed_at": "x", "idfm_observed_at": None, "confirmed": 1}
    m = tmp_path / "m.json"
    H.append_metrics([row], m)
    assert len(H.append_metrics([row, {**row, "sncf_observed_at": "y"}], m)["observations"]) == 2


def test_timelapse_and_series_order(tmp_path):
    rows = [{"region": "x", "sncf_observed_at": t, "idfm_observed_at": None, "night": n, "published": 10,
             "confirmed": c, "possible": c, "points_closed": 0, "stations_affected": 0, "station_states": st}
            for t, n, c, st in (("2026-11-17T09:30:00+00:00", False, 9, {"A": "DOUBT"}),
                                ("2026-11-16T23:30:00+00:00", True, 7, {"A": "CLOSED", "B": "DOUBT"}))]
    H.append_metrics(rows, tmp_path / "metrics.json")
    tl = H.region_timelapse("x", tmp_path)
    assert [f["confirmed"] for f in tl["frames"]] == [7, 9] and tl["frames"][0]["night"]
    assert tl["frames"][0]["stations"] == {"A": "CLOSED", "B": "DOUBT"}
    assert [o["confirmed"] for o in H.region_series("x", tmp_path)["observations"]] == [7, 9]
