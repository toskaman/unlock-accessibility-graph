"""France-wide comparison: every built region, same method, same day.

    python scripts/regions_report.py      → data/normalized/regions/summary.json (+ a table on stdout)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from unlock.config import NORMALIZED_DIR, STORE_PATH  # noqa: E402
from unlock.db import GraphStore  # noqa: E402
from unlock.engine.service import UnlockService  # noqa: E402
from unlock.network.service import NetworkService  # noqa: E402
from unlock.regions import REGIONS, compare_row, paths  # noqa: E402


def audit(code: str) -> dict:
    gi = json.loads((paths(code)["normalized"] / "graph_input.json").read_text(encoding="utf-8"))
    st = {s["id"]: s for s in gi["stations"]}
    weak = [{"station": st[m["station_id"]]["name"], "distance_m": m["distance_m"], "name_score": m["name_score"]}
            for m in gi["station_zone"] if m["name_score"] < 0.75 or m["distance_m"] > 400]
    return {"matches": len(gi["station_zone"]), "weak_matches": weak}


def main() -> None:
    rows = []
    stores = [("idf", "Île-de-France", Path(STORE_PATH))] + [(c, r["name"], paths(c)["store"]) for c, r in REGIONS.items()]
    for code, name, store in stores:
        if not store.exists():
            continue
        with GraphStore(store, read_only=True) as db:
            ns = NetworkService(db, UnlockService(db))
            rows.append({**compare_row(ns, code), "name": name,
                **({"audit": audit(code)} if code != "idf" else {}),
            })
    out = NORMALIZED_DIR / "regions" / "summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"format": "unlock-regions-summary/1", "regions": rows}, ensure_ascii=False, indent=1),
                   encoding="utf-8", newline="\n")
    print(f"{'region':28} {'acc.st':>6} {'published':>9} {'confirmed':>9} {'%':>6} {'lifts':>5} {'out':>4} {'topo':>9}")
    for r in rows:
        print(f"{r['name'][:28]:28} {r['accessible_stations']:>6} {r['published']:>9} {r['confirmed']:>9} "
              f"{(r['share_confirmed'] or 0) * 100:>5.1f}% {r['sncf_lifts']:>5} {r['sncf_lifts_out']:>4} "
              f"{r['with_platform_exit_topology']:>4}/{r['accessible_stations_with_lifts']:<4}")
    print(f"-> {out}")


if __name__ == "__main__":
    main()
