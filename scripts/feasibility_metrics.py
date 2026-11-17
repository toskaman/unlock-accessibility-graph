"""Reproducible metrics for docs/research/DATA_FEASIBILITY.md (numerator/denominator for every ratio)."""
import csv, io, json, sys, zipfile
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from unlock.config import RAW_DIR, NORMALIZED_DIR, IDF_DEPARTEMENTS  # noqa: E402
from unlock.ingest import netex  # noqa: E402

def ratio(n, d): return {"numerator": n, "denominator": d, "pct": round(100 * n / d, 1) if d else None}

out = {}
# GTFS
with zipfile.ZipFile(RAW_DIR / "gtfs" / "IDFM-gtfs.zip") as z:
    names = sorted(z.namelist())
    rd = lambda n: list(csv.DictReader(io.TextIOWrapper(z.open(n), encoding="utf-8-sig")))
    stops, paths, cal = rd("stops.txt"), rd("pathways.txt"), rd("calendar.txt")
out["gtfs"] = {"files": names, "has_levels_txt": "levels.txt" in names,
               "stops": len(stops), "stops_by_location_type": dict(Counter(s["location_type"] for s in stops)),
               "wheelchair_boarding_location_type_0": dict(Counter(s["wheelchair_boarding"] for s in stops if s["location_type"] == "0")),
               "pathways": len(paths), "pathway_modes": dict(Counter(p["pathway_mode"] for p in paths)),
               "elevator_pathways_mode_5": sum(1 for p in paths if p["pathway_mode"] == "5"),
               "calendar_span": [min(c["start_date"] for c in cal), max(c["end_date"] for c in cal)]}
# NeTEx + status
pub, places = netex.parse(RAW_DIR / "sncf" / "SNCF_GC_accessibilite_gares.xml")
status = list(csv.DictReader(open(RAW_DIR / "sncf" / "etat-fonctionnement-elevatique-gare.csv", encoding="utf-8-sig"), delimiter=";"))
lift_ids = [l.id for p in places for l in p.lifts]
sids = [r["id"] for r in status]
idf = [p for p in places if p.insee[:2] in IDF_DEPARTEMENTS]
out["sncf"] = {
    "netex_published": pub, "stop_places": len(places), "stop_places_idf": len(idf),
    "stop_places_missing_coords": sum(1 for p in places if p.lon is None or p.lat is None),
    "quays": sum(len(p.quays) for p in places), "lifts": len(lift_ids), "lift_ids_unique": len(set(lift_ids)),
    "status_rows": len(status), "status_ids_unique": len(set(sids)), "status_values": dict(Counter(r["etat_de_fonctionnement"] for r in status)),
    "lift_status_join": ratio(len(set(lift_ids) & set(sids)), len(set(lift_ids))),
    "status_rows_not_lifts_in_netex": len(set(sids) - set(lift_ids)),
    "status_gareid_join": ratio(sum(1 for r in status if r["gareid"] in {p.uuid for p in places}), len(status)),
    "quay_step_free_values": dict(Counter(q.assessment.limits["StepFreeAccess"] if q.assessment else "NONE" for p in places for q in p.quays)),
    "quay_lift_free_values": dict(Counter(q.assessment.limits["LiftFreeAccess"] if q.assessment else "NONE" for p in places for q in p.quays)),
}
rep = json.loads((NORMALIZED_DIR / "quality_report.json").read_text(encoding="utf-8"))
doc = json.loads((NORMALIZED_DIR / "graph_input.json").read_text(encoding="utf-8"))
c = rep["counts"]
out["pilot_idf"] = {
    "stations": c["netex_stop_places_in_region"], "lifts": c["lifts"], "quays": c["quays"],
    "lifts_two_resolved_ends": ratio(c["lifts_two_resolved_ends"], c["lifts"]),
    "lifts_one_resolved_end": ratio(c["lifts_one_resolved_end"], c["lifts"]),
    "serves_derivations": rep["serves_derivations"], "space_roles": rep["space_roles"],
    "unmatched_track_tokens": rep["unmatched_token_count"],
    "station_to_idfm_zone": ratio(c["stations_matched_to_zone"], c["netex_stop_places_in_region"]),
    "station_zone_name_score_lt_0_5": sum(1 for x in doc["station_zone"] if x["name_score"] < 0.5),
    "status_states": {k[7:]: v for k, v in c.items() if k.startswith("status_") and k[7:] in ("AVAILABLE", "UNAVAILABLE", "UNKNOWN")},
    "zones": c["zones"], "lines_non_bus": c["lines_non_bus"],
}
p = Path(__file__).resolve().parents[1] / "docs" / "research" / "feasibility_metrics.json"
p.write_text(json.dumps(out, indent=1, ensure_ascii=False))
print(json.dumps(out, indent=1, ensure_ascii=False))
