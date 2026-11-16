"""SYNTHETIC regional network for tests (not official data).

    Alpha(Z2) --R1-- Testville(Z1) --R1-- Beta(Z3) ==M1== Gamma(Z4) --T1-- Delta(Z5, not boardable)

R1 = rail (one platform node per station), M1 = metro with one quay per direction, T1 = tram.
Testville is the SNCF fixture station of conftest.py (same IDFM zone id "Z1").
Outage feed: one RATP lift at Beta "Quai 1, direction Gamma" (M1 quay towards Gamma), one Gares & Connexions
lift at Testville "Souterrain <> Hall" (the resolver must find L3, the only lift to the exit; the SNCF fixture
says L3 works -> GHOST).
"""
from __future__ import annotations

ST = {"Z1": "Testville", "Z2": "Alpha", "Z3": "Beta", "Z4": "Gamma", "Z5": "Delta"}


def network() -> dict:
    stations = [{"id": z, "gtfs_id": f"IDFM:{z}", "name": n, "lat": 48.8 + i * 0.01, "lon": 2.3 + i * 0.01}
                for i, (z, n) in enumerate(sorted(ST.items()))]
    P = lambda pid, z, modes, lines, wc="ACCESSIBLE": {"id": pid, "station_id": z, "name": ST[z], "wheelchair": wc,
                                                        "lat": 48.8, "lon": 2.3, "modes": modes, "lines": lines,
                                                        "boardable": wc == "ACCESSIBLE"}
    platforms = [P("R:Z1", "Z1", ["RAIL"], ["R1"]), P("R:Z2", "Z2", ["RAIL"], ["R1"]), P("R:Z3", "Z3", ["RAIL"], ["R1"]),
                 P("M:Z3a", "Z3", ["METRO"], ["M1"]), P("M:Z3b", "Z3", ["METRO"], ["M1"]),
                 P("M:Z4a", "Z4", ["METRO"], ["M1"]), P("M:Z4b", "Z4", ["METRO"], ["M1"]),
                 P("T:Z4", "Z4", ["TRAM"], ["T1"]), P("T:Z5", "Z5", ["TRAM"], ["T1"], "NOT_ACCESSIBLE")]
    lines = [{"id": "R1", "short_name": "R1", "long_name": "Rail", "mode": "RAIL", "color": "FF0000", "text_color": "FFFFFF", "operator": "x"},
             {"id": "M1", "short_name": "1", "long_name": "Metro", "mode": "METRO", "color": "00FF00", "text_color": "000000", "operator": "x"},
             {"id": "T1", "short_name": "T1", "long_name": "Tram", "mode": "TRAM", "color": "0000FF", "text_color": "FFFFFF", "operator": "x"}]
    pat = lambda pid, line, d, stops, head, term: {"id": pid, "line_id": line, "direction": d, "trips": 10, "headsign": head,
                                                   "terminus_station": term, "stops": stops}
    patterns = [pat("R1:0", "R1", "0", ["R:Z2", "R:Z1", "R:Z3"], "Beta", "Z3"),
                pat("R1:1", "R1", "1", ["R:Z3", "R:Z1", "R:Z2"], "Alpha", "Z2"),
                pat("M1:0", "M1", "0", ["M:Z3a", "M:Z4a"], "Gamma", "Z4"),
                pat("M1:1", "M1", "1", ["M:Z4b", "M:Z3b"], "Beta", "Z3"),
                pat("T1:0", "T1", "0", ["T:Z4", "T:Z5"], "Delta", "Z5")]
    return {"format": "unlock-network/1", "stations": stations, "platforms": platforms, "lines": lines,
            "patterns": patterns, "datasets": [], "counts": {}}


def _dis(did, ref, zone, text, begin="20260901T080000", updated="20261009T090000"):
    return {"id": did, "status": "active", "tags": ["Ascenseur"], "reference": ref,
            "application_periods": [{"begin": begin, "end": "20270901T080000"}], "updated_at": updated,
            "impacted_objects": [{"pt_object": {"id": f"stop_area:IDFM:{zone}", "name": ST[zone], "embedded_type": "stop_area"}}],
            "messages": [{"text": text, "channel": {"name": "moteur"}}, {"text": "Panne", "channel": {"name": "titre"}}]}


def line_reports() -> dict:
    dis = [_dis("d1", "RATP_elevator_501", "Z3", "BETA Panne de l'ascenseur situé Quai 1, direction Gamma"),
           _dis("d2", "RATP_elevator_501", "Z3", "BETA Panne ascenseur Quai 1, dir. Gamma", begin="20260801T080000"),
           _dis("d3", "GARES_CONNEXIONS_elevator_77_20261001", "Z1",
                "GARE DE TESTVILLE Panne de l'ascenseur situé Souterrain <> Hall"),
           {**_dis("d4", "x", "Z2", "Travaux"), "tags": ["Travaux"], "updated_at": "20261116T080000"}]
    lr = [{"line": {"id": "line:M1", "links": [{"type": "disruption", "id": "d1"}, {"type": "disruption", "id": "d2"}]}, "pt_objects": []},
          {"line": {"id": "line:R1", "links": [{"type": "disruption", "id": "d3"}, {"type": "disruption", "id": "d4"}]}, "pt_objects": []}]
    return {"fetched_at": "2026-11-16T19:00:00+00:00", "source": "fixture://prim",
            "pages": [{"pagination": {}, "disruptions": dis, "line_reports": lr}]}
