"""Second-region network builder on a tiny synthetic national GTFS (not official data)."""
import csv
import io
import zipfile

from unlock.regions import REGIONS, build_network_region


def _zip(path, files):
    with zipfile.ZipFile(path, "w") as z:
        for name, rows in files.items():
            buf = io.StringIO()
            w = csv.DictWriter(buf, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
            z.writestr(name, buf.getvalue())


def test_region_network_keeps_matched_stations_and_takes_boardability_from_netex(tmp_path):
    S = lambda i, n, parent="", lt="0": {"stop_id": i, "stop_name": n, "stop_lat": "45.7", "stop_lon": "4.8",
                                         "location_type": lt, "parent_station": parent}
    stops = [S("StopArea:OCE1", "A", lt="1"), S("StopPoint:OCETrain TER-1", "A", "StopArea:OCE1"),
             S("StopArea:OCE2", "B", lt="1"), S("StopPoint:OCETrain TER-2", "B", "StopArea:OCE2"),
             S("StopArea:OCE9", "Elsewhere", lt="1"), S("StopPoint:OCETrain TER-9", "Elsewhere", "StopArea:OCE9")]
    _zip(tmp_path / "g.zip", {
        "agency.txt": [{"agency_id": "1", "agency_name": "SNCF"}],
        "routes.txt": [{"route_id": "R", "agency_id": "1", "route_short_name": "C1", "route_long_name": "A - B",
                        "route_type": "2", "route_color": "", "route_text_color": ""}],
        "trips.txt": [{"route_id": "R", "service_id": "s", "trip_id": "t1", "trip_headsign": "1", "direction_id": "0"}],
        "stop_times.txt": [{"trip_id": "t1", "stop_id": f"StopPoint:OCETrain TER-{i}", "stop_sequence": str(k)}
                           for k, i in enumerate((1, 9, 2))],
        "stops.txt": stops})
    gi = {"stations": [{"id": "SA", "wheelchair": "ACCESSIBLE"}, {"id": "SB", "wheelchair": "INACCESSIBLE"}],
          "station_zone": [{"station_id": "SA", "zone_id": "OCE1"}, {"station_id": "SB", "zone_id": "OCE2"}]}
    rid = tmp_path / "f.json"
    rid.write_text('[{"code_uic_complet": "0000000001", "total_voyageurs_2025": 3650}]')
    net = build_network_region(tmp_path / "g.zip", gi, rid)
    assert [s["id"] for s in net["stations"]] == ["OCE1", "OCE2"]            # OCE9 is outside the region
    p = {x["id"]: x for x in net["platforms"]}
    assert set(p) == {"StopPoint:OCETrain_TER-1", "StopPoint:OCETrain_TER-2"}  # ids made key-safe
    assert p["StopPoint:OCETrain_TER-1"]["boardable"] and not p["StopPoint:OCETrain_TER-2"]["boardable"]
    assert net["patterns"][0]["stops"] == ["StopPoint:OCETrain_TER-1", "StopPoint:OCETrain_TER-2"]
    assert net["stations"][0]["entries_per_day"] == 10 and net["stations"][0]["entries_dataset"] == "sncf_frequentation"
    assert "ara" in REGIONS and REGIONS["ara"]["departements"][0] == "01"
