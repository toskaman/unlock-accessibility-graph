"""The zero-install demo recomputes journeys and reaches in the browser (frontend/src/static/engine.ts).
This check runs the server engine and the browser engine on the same exported graph and compares them:
every origin's reach (confirmed + possible, best and feed views) and 300 random station pairs × 2 views
(verdict and every leg). Result: docs/research/static_engine_check.json.

    python scripts/export_static.py && python scripts/check_static_engine.py
"""
from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from unlock.config import STORE_PATH  # noqa: E402
from unlock.db import GraphStore  # noqa: E402
from unlock.engine.service import UnlockService  # noqa: E402
from unlock.network import engine as E  # noqa: E402
from unlock.network.service import NetworkService  # noqa: E402


def main() -> None:
    ref = {"reach": {}, "journeys": []}
    with GraphStore(STORE_PATH, read_only=True) as db:
        ns = NetworkService(db, UnlockService(db))
        for v in ("best", "feed"):
            ns.view_summary(v)
            conf, poss = E.usable_sets(ns._cache[f"sum:{v}"]["_states"], ns.net.platforms)
            ref["reach"][v] = {o: [len(E.reach_set(ns.net, conf, o)), len(E.reach_set(ns.net, poss, o))]
                               for o in sorted(ns.net.station_platforms)}
        rnd = random.Random(7)
        ids = sorted(ns.net.station_platforms)
        for _ in range(300):
            a, b = rnd.sample(ids, 2)
            for v in ("best", "feed"):
                j = ns.check_journey(a, b, v)
                ref["journeys"].append({"a": a, "b": b, "view": v, "verdict": j["verdict"],
                                        "legs": [[l["board"], l["alight"], l["line"]] for l in j["legs"]]})
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "ref.json").write_text(json.dumps(ref), encoding="utf-8")
        fe = ROOT / "frontend"
        subprocess.run(["npx", "tsc", "--ignoreConfig", "src/static/engine.ts", "--outDir", tmp, "--target", "es2022",
                        "--module", "es2022", "--skipLibCheck"], cwd=fe, check=True, shell=os.name == "nt")
        out = Path(tmp, "out.json")
        env = {**os.environ, "ENGINE_JS": Path(tmp, "engine.js").as_uri(), "REF": str(Path(tmp, "ref.json")),
               "GRAPH": str(fe / "static-data" / "idf" / "graph.json"), "OUT": str(out)}
        subprocess.run(["node", "scripts/check-static-engine.mjs"], cwd=fe, check=True, env=env)
        res = json.loads(out.read_text(encoding="utf-8"))
    res["checked_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    res["method"] = ("Same exported graph; server engine (backend/unlock/network/engine.py) vs browser engine "
                     "(frontend/src/static/engine.ts): reach sizes of every origin, confirmed and possible, best and feed "
                     "views; 300 random pairs × 2 views: verdict and every leg (board, alight, line).")
    (ROOT / "docs" / "research" / "static_engine_check.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    ok = res["reach_identical"] == res["reach_total"] and res["journeys_identical"] == res["journeys_total"]
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
