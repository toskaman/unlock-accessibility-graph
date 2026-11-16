"""Import data/normalized/graph_input.json into the persistent Relate store.

Usage: python scripts/build_graph.py [--store PATH] [--backup]
Re-running is safe: the import is idempotent (MERGE on constrained ids).
"""
import argparse, json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from unlock.config import STORE_PATH  # noqa: E402
from unlock.db import GraphStore, backup  # noqa: E402
from unlock.ingest.load import run_import  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--store", default=str(STORE_PATH))
ap.add_argument("--backup", action="store_true", help="copy the existing store before importing")
a = ap.parse_args()
if a.backup:
    print("backup:", backup(Path(a.store)))
t = time.time()
with GraphStore(a.store) as db:
    res = run_import(db)
print(json.dumps(res, indent=1))
print(f"store {a.store} imported in {time.time()-t:.1f}s")
