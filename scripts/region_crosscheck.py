"""Re-derive, in Cypher, the confirmed step-free reach of EVERY origin station under every view and compare it with
the engine's exact computation. Usage: python scripts/region_crosscheck.py -> docs/research/region_crosscheck.json"""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from unlock.config import ROOT, STORE_PATH  # noqa: E402
from unlock.db import GraphStore  # noqa: E402
from unlock.engine.service import UnlockService  # noqa: E402
from unlock.network import engine as E  # noqa: E402
from unlock.network.service import NetworkService  # noqa: E402

out = {"store": str(STORE_PATH.name), "views": {}}
with GraphStore(STORE_PATH, read_only=True) as db:
    ns = NetworkService(db, UnlockService(db))
    out["feed_id"] = ns.feed["id"] if ns.feed else None
    for view in ("published", "best", "feed"):
        ns.view_summary(view)
        conf, _ = E.usable_sets(ns._cache[f"sum:{view}"]["_states"], ns.net.platforms)
        _, per = E.reach_counts(ns.net, conf)
        t0, mism, n, pairs = time.time(), [], 0, 0
        for origin in sorted(ns.net.station_platforms):
            eng = E.reach_set(ns.net, conf, origin)
            cy, _ = ns.cypher_reach(origin, conf)
            n += 1
            pairs += len(cy)
            if eng != cy or len(eng) != per.get(origin, 0):
                mism.append({"origin": origin, "engine": len(eng), "cypher": len(cy), "reach_counts": per.get(origin, 0)})
        out["views"][view] = {"origins": n, "ordered_pairs_cypher": pairs, "mismatches": mism,
                              "seconds": round(time.time() - t0, 1)}
        print(view, out["views"][view]["origins"], pairs, len(mism), flush=True)
(ROOT / "docs" / "research" / "region_crosscheck.json").write_text(json.dumps(out, indent=1))
