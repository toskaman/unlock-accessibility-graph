"""Département recovery for the 2026-11-24 NeTEx layout (SYNTHETIC fixtures, not official data).

The new SNCF layout (``FR::monomodalStopPlace:<uuid>:LOC``) carries no INSEE
code; tests cover the UIC-postcode chain, the DRG quarantine, the ZdC fallback
and the unknown-is-dropped rule, plus the lift-id normalisation.
"""
import csv
import io
import json
import zipfile

from unlock.config import IDF_DEPARTEMENTS
from unlock.ingest import departments, netex
from unlock.ingest.departments import DRG_DEPARTMENTS, DeptAssignment, assign_departments, dept_of_postal
from unlock.regions import REGIONS


def _place(uuid, name, lon, lat, insee=""):
    return netex.StopPlace(id=f"FR::{'monomodalStopPlace' if not insee else insee + ':LMO'}:{uuid}:LOC",
                           uuid=uuid, insee=insee, name=name, lon=lon, lat=lat,
                           transport_mode="rail", stop_place_type="railStation", assessment=None)


def _zip(path, files):
    with zipfile.ZipFile(path, "w") as z:
        for name, text in files.items():
            z.writestr(name, text)


def _stops(rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["stop_id", "stop_name", "stop_lat", "stop_lon", "location_type",
                                        "parent_station"])
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def _raw(tmp_path, nat_areas=(), freq=(), idf_areas=(), zdc=()):
    (tmp_path / "sncf_national").mkdir()
    (tmp_path / "gtfs").mkdir()
    (tmp_path / "idfm").mkdir()
    _zip(tmp_path / "sncf_national" / "sncf-gtfs.zip", {"stops.txt": _stops(nat_areas)})
    (tmp_path / "sncf_national" / "frequentation-gares.json").write_text(json.dumps(freq))
    _zip(tmp_path / "gtfs" / "IDFM-gtfs.zip", {"stops.txt": _stops(idf_areas)})
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["zdcid", "zdcname", "zdcpostalregion", "zdctype"], delimiter=";")
    w.writeheader()
    w.writerows(zdc)
    (tmp_path / "idfm" / "zones-de-correspondance.csv").write_text(buf.getvalue())
    return tmp_path


def _area(sid, name, lat="45.7", lon="4.8"):
    return {"stop_id": sid, "stop_name": name, "stop_lat": lat, "stop_lon": lon, "location_type": "1",
            "parent_station": ""}


def test_uic_postal_chain_assigns_from_national_gtfs(tmp_path):
    raw = _raw(tmp_path,
               nat_areas=[_area("StopArea:OCE87680001", "Lyon Test")],
               freq=[{"code_uic_complet": "87680001", "code_postal": "69001",
                      "direction_regionale_gares": "DRG AURA BFC"}])
    got = assign_departments([_place("u1", "Lyon Test", 4.8, 45.7)], raw)
    assert got == {"u1": DeptAssignment("69", "UIC_POSTAL", got["u1"].evidence)}
    assert "87680001" in got["u1"].evidence and "69001" in got["u1"].evidence


def test_drg_mismatch_quarantines_instead_of_misplacing(tmp_path):
    # Pont-sur-Yonne, 24 Nov 2026: the Fréquentation row says 14130 (Calvados)
    # for a "DRG AURA BFC" station. Must not land in Normandie.
    raw = _raw(tmp_path,
               nat_areas=[_area("StopArea:OCE87683136", "Pont-sur-Yonne", lat="48.28", lon="3.20")],
               freq=[{"code_uic_complet": "87683136", "code_postal": "14130",
                      "direction_regionale_gares": "DRG AURA BFC"}])
    got = assign_departments([_place("u2", "Pont-sur-Yonne", 3.20, 48.28)], raw)
    assert got["u2"].dept == "" and got["u2"].derivation == "QUARANTINED_DRG_MISMATCH"


def test_unknown_drg_is_accepted_not_quarantined(tmp_path):
    # A directorate label the table does not know yet must not nuke a region.
    raw = _raw(tmp_path,
               nat_areas=[_area("StopArea:OCE87680002", "Lyon Test")],
               freq=[{"code_uic_complet": "87680002", "code_postal": "69002",
                      "direction_regionale_gares": "DRG SOMETHING NEW"}])
    got = assign_departments([_place("u3", "Lyon Test", 4.8, 45.7)], raw)
    assert (got["u3"].dept, got["u3"].derivation) == ("69", "UIC_POSTAL")


def test_zdc_postalregion_fallback_for_transilien_stops(tmp_path):
    # Absent from the national GTFS, present in the IDFM GTFS + ZdC.
    raw = _raw(tmp_path,
               idf_areas=[_area("IDFM:41234", "Savigny Test", lat="48.58", lon="2.57")],
               zdc=[{"zdcid": "41234", "zdcname": "Savigny Test", "zdcpostalregion": "771108",
                     "zdctype": "railStation"}])
    got = assign_departments([_place("u4", "Savigny Test", 2.57, 48.58)], raw)
    assert (got["u4"].dept, got["u4"].derivation) == ("77", "ZDC_POSTALREGION")


def test_unmatched_place_gets_no_assignment(tmp_path):
    raw = _raw(tmp_path)
    assert assign_departments([_place("u5", "Nowhere Halt", 0.0, 46.0)], raw) == {}


def test_places_with_insee_are_skipped_without_touching_references(tmp_path):
    assert assign_departments([_place("u6", "Old Layout", 2.3, 48.8, insee="75056")], tmp_path) == {}


def test_missing_reference_files_do_not_crash(tmp_path):
    assert assign_departments([_place("u7", "Lyon Test", 4.8, 45.7)], tmp_path) == {}


def test_dept_of_postal():
    assert dept_of_postal("75001") == "75"
    assert dept_of_postal("20000") == "2A" and dept_of_postal("20190") == "2A"
    assert dept_of_postal("20200") == "2B"
    assert dept_of_postal("98000") == "98"
    assert dept_of_postal("") == "" and dept_of_postal(None) == ""


def test_drg_table_matches_the_region_map():
    depts = {"idf": set(IDF_DEPARTEMENTS)}
    depts.update({c: set(v["departements"]) for c, v in REGIONS.items()})
    expect = {"DEX GIF": {"idf"}, "ETAB GARES PARIS": {"idf"}, "DRG AURA BFC": {"ara", "bfc"},
              "DRG B-CVL-PDL": {"bre", "cvl", "pdl"}, "DRG GRAND EST": {"ges"},
              "DRG HDF-NORMANDIE": {"hdf", "nor"}, "DRG NLLE AQUITAINE": {"naq"},
              "DRG OCCITANIE": {"occ"}, "DRG SUD": {"pac"}}
    assert set(DRG_DEPARTMENTS) == set(expect)
    for drg, codes in expect.items():
        want = set().union(*(depts[c] for c in codes)) | ({"98"} if drg == "DRG SUD" else set())
        assert DRG_DEPARTMENTS[drg] == frozenset(want), drg


def test_netex_parses_both_id_layouts(tmp_path):
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<PublicationDelivery xmlns="http://www.netex.org.uk/netex">
  <PublicationTimestamp>2026-11-24T12:00:00Z</PublicationTimestamp>
  <dataObjects><GeneralFrame id="g" version="any"><members>
    <StopPlace id="FR:69123:LMO:old-uuid:LOC" version="any"><Name>Old</Name>
      <quays/><placeEquipments>
        <EquipmentPlace id="e1" version="any"><placeEquipments>
          <LiftEquipment id="lift-old" version="any"><Name>L</Name></LiftEquipment>
        </placeEquipments></EquipmentPlace>
      </placeEquipments></StopPlace>
    <StopPlace id="FR::monomodalStopPlace:new-uuid:LOC" version="any"><Name>New</Name>
      <Centroid version="any"><Location><Longitude>4.8</Longitude><Latitude>45.7</Latitude></Location></Centroid>
      <placeEquipments>
        <EquipmentPlace id="e2" version="any"><placeEquipments>
          <LiftEquipment id="SNCF-GC:LiftEquipment:lift-new:LOC" version="any"><Name>L</Name></LiftEquipment>
        </placeEquipments></EquipmentPlace>
      </placeEquipments></StopPlace>
  </members></GeneralFrame></dataObjects>
</PublicationDelivery>"""
    p = tmp_path / "n.xml"
    p.write_text(xml, encoding="utf-8")
    _, places = netex.parse(p)
    by_uuid = {x.uuid: x for x in places}
    assert by_uuid["old-uuid"].insee == "69123"
    assert by_uuid["old-uuid"].lifts[0].id == "lift-old"          # bare uuid untouched
    assert by_uuid["new-uuid"].insee == ""                        # no geography in the new layout
    assert (by_uuid["new-uuid"].lat, by_uuid["new-uuid"].lon) == (45.7, 4.8)
    assert by_uuid["new-uuid"].lifts[0].id == "lift-new"          # qualified id reduced to its uuid


def test_build_pilot_uses_assigned_departments(tmp_path, monkeypatch):
    from unlock.ingest import normalize
    raw = tmp_path / "raw"
    (raw / "sncf").mkdir(parents=True)
    (raw / "sncf" / "SNCF_GC_accessibilite_gares.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<PublicationDelivery xmlns="http://www.netex.org.uk/netex">
  <PublicationTimestamp>2026-11-24T12:00:00Z</PublicationTimestamp>
  <dataObjects><GeneralFrame id="g" version="any"><members>
    <StopPlace id="FR::monomodalStopPlace:kept:LOC" version="any"><Name>Lyon Test</Name>
      <Centroid version="any"><Location><Longitude>4.8</Longitude><Latitude>45.7</Latitude></Location></Centroid>
      <TransportMode>rail</TransportMode><StopPlaceType>railStation</StopPlaceType></StopPlace>
    <StopPlace id="FR::monomodalStopPlace:dropped:LOC" version="any"><Name>Nowhere Halt</Name>
      <Centroid version="any"><Location><Longitude>0.0</Longitude><Latitude>46.0</Latitude></Location></Centroid>
      <TransportMode>rail</TransportMode><StopPlaceType>railStation</StopPlaceType></StopPlace>
  </members></GeneralFrame></dataObjects>
</PublicationDelivery>""", encoding="utf-8")
    (raw / "sncf" / "etat-fonctionnement-elevatique-gare.csv").write_text("gareid;id;libelle\n", encoding="utf-8")
    _raw(raw, nat_areas=[_area("StopArea:OCE87680001", "Lyon Test")],
         freq=[{"code_uic_complet": "87680001", "code_postal": "69001",
                "direction_regionale_gares": "DRG AURA BFC"}])
    man = tmp_path / "manifest.json"
    man.write_text(json.dumps({
        "sncf_netex_accessibility": {"key": "sncf_netex_accessibility", "file": "sncf/x.xml",
                                     "sha256": "a" * 64, "retrieved_at": "2026-11-24T00:00:00+00:00"},
        "sncf_lift_status": {"key": "sncf_lift_status", "file": "sncf/y.csv", "sha256": "b" * 64,
                             "retrieved_at": "2026-11-24T00:00:00+00:00"}}), encoding="utf-8")
    monkeypatch.setattr(normalize, "MANIFEST_PATH", man)
    out = tmp_path / "out"
    rep = normalize.build(raw_dir=raw, out_dir=out, with_gtfs=False, departements=("69",))
    doc = json.loads((out / "graph_input.json").read_text(encoding="utf-8"))
    assert [s["uuid"] for s in doc["stations"]] == ["kept"]
    assert doc["stations"][0]["department"] == "69"
    assert doc["stations"][0]["department_derivation"] == "UIC_POSTAL"
    assert rep["counts"]["netex_stop_places_in_region"] == 1
    assert rep["counts"]["stations_dept_uic_postal"] == 1
    assert rep["counts"]["stations_dept_unknown"] == 1
    assert rep["dept_unknown_stations"] == ["Nowhere Halt"]


def test_build_keeps_old_files_on_netex_id_without_references(tmp_path, monkeypatch):
    from unlock.ingest import normalize
    raw = tmp_path / "raw"
    (raw / "sncf").mkdir(parents=True)
    (raw / "sncf" / "SNCF_GC_accessibilite_gares.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<PublicationDelivery xmlns="http://www.netex.org.uk/netex">
  <PublicationTimestamp>2026-11-15T19:00:00Z</PublicationTimestamp>
  <dataObjects><GeneralFrame id="g" version="any"><members>
    <StopPlace id="FR:69123:LMO:kept:LOC" version="any"><Name>Old</Name>
      <Centroid version="any"><Location><Longitude>4.8</Longitude><Latitude>45.7</Latitude></Location></Centroid>
      <TransportMode>rail</TransportMode><StopPlaceType>railStation</StopPlaceType></StopPlace>
  </members></GeneralFrame></dataObjects>
</PublicationDelivery>""", encoding="utf-8")
    (raw / "sncf" / "etat-fonctionnement-elevatique-gare.csv").write_text("gareid;id;libelle\n", encoding="utf-8")
    man = tmp_path / "manifest.json"
    man.write_text(json.dumps({
        "sncf_netex_accessibility": {"key": "sncf_netex_accessibility", "file": "sncf/x.xml",
                                     "sha256": "a" * 64, "retrieved_at": "2026-11-15T00:00:00+00:00"},
        "sncf_lift_status": {"key": "sncf_lift_status", "file": "sncf/y.csv", "sha256": "b" * 64,
                             "retrieved_at": "2026-11-15T00:00:00+00:00"}}), encoding="utf-8")
    monkeypatch.setattr(normalize, "MANIFEST_PATH", man)
    out = tmp_path / "out"
    rep = normalize.build(raw_dir=raw, out_dir=out, with_gtfs=False, departements=("69",))
    doc = json.loads((out / "graph_input.json").read_text(encoding="utf-8"))
    assert [s["uuid"] for s in doc["stations"]] == ["kept"]   # no GTFS/frequentation/ZdC on disk
    assert rep["counts"]["stations_dept_netex_id"] == 1
