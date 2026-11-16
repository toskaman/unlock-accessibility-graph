"""Measure import, startup, traversal and scenario timings on the real store copy.
Usage: python scripts/benchmark.py [--runs 20]   -> docs/BENCHMARK.json"""
import argparse, json, os, platform, shutil, statistics, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from unlock.config import ROOT, STORE_PATH  # noqa: E402
from unlock.db import GraphStore  # noqa: E402
from unlock.engine import graph as G  # noqa: E402
from unlock.engine.service import UnlockService  # noqa: E402
from unlock.ingest.load import run_import  # noqa: E402

ap = argparse.ArgumentParser(); ap.add_argument("--runs", type=int, default=20); a = ap.parse_args()
def stats(xs): xs = sorted(xs); return {"n": len(xs), "median_ms": round(statistics.median(xs), 1), "p95_ms": round(xs[max(0, int(0.95 * len(xs)) - 1)], 1)}
tmp = Path(tempfile.mkdtemp())
res = {"hardware": {"platform": platform.platform(), "python": platform.python_version(), "cpus": os.cpu_count()}}
t = time.perf_counter()
with GraphStore(tmp / "fresh.rl") as db:
    run_import(db); res["graph_counts"] = db.counts()
res["import_fresh_store_ms"] = round((time.perf_counter() - t) * 1000, 1)
res["store_bytes"] = (tmp / "fresh.rl").stat().st_size
shutil.copy(STORE_PATH, tmp / "b.rl")
t = time.perf_counter(); db = GraphStore(tmp / "b.rl"); svc = UnlockService(db)
res["service_startup_ms"] = round((time.perf_counter() - t) * 1000, 1)
route = []
for _ in range(min(a.runs, 5)):
    t = time.perf_counter(); G.load_pairs(db); route.append((time.perf_counter() - t) * 1000)
res["route_traversal_all_stations"] = stats(route)
lift = next(l for l in svc.lifts.values() if (l.name or "").startswith("ASC.PMR 4556"))
juv = [lift.station_id]
one = []
for _ in range(a.runs):
    t = time.perf_counter(); G.load_pairs(db, juv); one.append((time.perf_counter() - t) * 1000)
res["route_traversal_one_station"] = stats(one)
sim, rank, expl = [], [], []
for _ in range(a.runs):
    t = time.perf_counter(); sc = svc.create_scenario("bench", {lift.id: "UNAVAILABLE"}); an = svc.analyze(sc["id"]); sim.append((time.perf_counter() - t) * 1000)
    t = time.perf_counter(); svc.rank(sc["id"]); rank.append((time.perf_counter() - t) * 1000)
    t = time.perf_counter(); svc.explain_pair(an["lost_confirmed"][0], sc["id"], lift.id); expl.append((time.perf_counter() - t) * 1000)
    svc.delete_scenario(sc["id"])
res["create_and_analyze_scenario"] = stats(sim); res["rank_interventions"] = stats(rank); res["explain_pair_with_evidence"] = stats(expl)
db.close(); shutil.rmtree(tmp)
(ROOT / "docs" / "BENCHMARK.json").write_text(json.dumps(res, indent=1))
print(json.dumps(res, indent=1))
