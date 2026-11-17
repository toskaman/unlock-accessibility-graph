"""UNLOCK command line.

  python -m unlock fetch        download official source snapshots (data/raw)
  python -m unlock normalize    build data/normalized/graph_input.json
  python -m unlock import       import into the Relate store (idempotent)
  python -m unlock build        normalize (if data/raw exists) + import
  python -m unlock serve        run the API (+ built frontend) on 127.0.0.1:8000
  python -m unlock stats        print graph counts from the store
  python -m unlock mcp          MCP server (stdio, read-only store) for AI agents
  python -m unlock fetch-outages   PRIM lift outages (needs UNLOCK_PRIM_KEY or UNLOCK_PRIM_KEY_FILE)
  python -m unlock fetch-lifts     IDFM lift status (needs UNLOCK_IDFM_ODS_KEY or UNLOCK_IDFM_ODS_KEY_FILE)
  python -m unlock bulletin        daily accessibility bulletin (JSON + Markdown + HTML in reports/)
  python -m unlock record          append lift-status history + headline metrics of every built region
  python -m unlock refresh         fresh lift status (SNCF, + PRIM/IDFM when keys are set) → rebuild every region
  python -m unlock build-region ara   same method on another region (national SNCF data; see docs/REGIONS.md)
  python -m unlock alerts FILE     rider alerts for the usual trips listed in FILE (JSON, see docs/RIDER_ALERTS.md)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .config import ROOT, STORE_PATH


def main() -> None:
    ap = argparse.ArgumentParser(prog="unlock")
    ap.add_argument("command", choices=["fetch", "fetch-outages", "fetch-lifts", "bulletin", "alerts", "build-region", "refresh", "record", "normalize", "import", "build", "serve", "stats", "mcp"])
    ap.add_argument("file", nargs="?", help="alerts: trips file")
    ap.add_argument("--out", default=None, help="bulletin/alerts: output folder (default reports/)")
    ap.add_argument("--store", default=str(STORE_PATH))
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-gtfs", action="store_true")
    a = ap.parse_args()

    if a.command == "fetch":
        subprocess.run([sys.executable, str(ROOT / "scripts" / "fetch_sources.py")], check=True)
    if a.command == "fetch-lifts":
        from .network import idfm_lifts
        from .config import NORMALIZED_DIR
        print(f"IDFM lift status -> {idfm_lifts.fetch()}")
        net = json.loads((NORMALIZED_DIR / "network.json").read_text(encoding="utf-8"))
        print(json.dumps(idfm_lifts.normalize_file(net)["counts"], indent=1))
        return
    if a.command == "fetch-outages":
        from .network.prim import fetch as fetch_prim
        print(f"PRIM lift outages -> {fetch_prim()}")
        from .network.normalize_net import build_outages_file
        from .config import NORMALIZED_DIR
        net = json.loads((NORMALIZED_DIR / "network.json").read_text(encoding="utf-8"))
        doc = build_outages_file(net)
        print(json.dumps(doc["counts"], indent=1))
        from .network import feedwatch
        s = feedwatch.summary(feedwatch.append(doc))
        print(f"feed watch: {s['observations']} observations, lift content identical in {s['identical_lift_content']} "
              f"since {s['identical_since']}; last lift update {doc['feed_last_lift_update']}")
        return
    if a.command in ("normalize", "build"):
        from .config import RAW_DIR
        if (RAW_DIR / "sncf" / "SNCF_GC_accessibilite_gares.xml").exists():
            from .ingest.normalize import build
            rep = build(with_gtfs=not a.no_gtfs)
            print(json.dumps(rep["counts"], indent=1))
            if not a.no_gtfs and (RAW_DIR / "gtfs" / "IDFM-gtfs.zip").exists():
                from .network.normalize_net import build as build_net
                print(json.dumps(build_net(), indent=1))
        elif a.command == "normalize":
            sys.exit("No raw snapshots in data/raw — run `python -m unlock fetch` first.")
        else:
            print("data/raw not present: importing the committed snapshot data/normalized/graph_input.json "
                  "(run `python -m unlock fetch` to refresh from the publishers).")
    if a.command in ("import", "build"):
        from .db import GraphStore
        from .ingest.load import import_all
        with GraphStore(a.store) as db:
            print(json.dumps(import_all(db)["after"], indent=1))
    if a.command == "stats":
        from .db import GraphStore
        with GraphStore(a.store, read_only=True) as db:
            print(json.dumps(db.counts(), indent=1))
    if a.command == "refresh":
        import os
        steps = [[sys.executable, str(ROOT / "scripts" / "fetch_sources.py"), "--only", "sncf_lift_status"]]
        if os.environ.get("UNLOCK_PRIM_KEY") or os.environ.get("UNLOCK_PRIM_KEY_FILE"):
            steps.append([sys.executable, "-m", "unlock", "fetch-outages"])
        if os.environ.get("UNLOCK_IDFM_ODS_KEY") or os.environ.get("UNLOCK_IDFM_ODS_KEY_FILE"):
            steps.append([sys.executable, "-m", "unlock", "fetch-lifts"])
        steps.append([sys.executable, "-m", "unlock", "build", "--store", a.store])
        from .regions import REGIONS, paths
        built = [c for c in REGIONS if paths(c)["store"].exists()]
        if built:
            steps.append([sys.executable, "-m", "unlock", "build-region", ",".join(built)])
        steps.append([sys.executable, "-m", "unlock", "record", "--store", a.store])
        for s in steps:
            print("→", " ".join(s[1:]), flush=True)
            subprocess.run(s, check=True, cwd=ROOT)
        print("Done. Restart `python -m unlock serve` to load the new status (the server must be stopped while "
              "building: Relate allows one writer).")
        return
    if a.command == "record":
        from . import history as H
        from .db import GraphStore
        from .engine.service import UnlockService
        from .network.service import NetworkService
        from .regions import REGIONS, paths
        sn = H.append_sncf(H.sncf_observation())
        rows = []
        for code, store in [("idf", Path(a.store))] + [(c, paths(c)["store"]) for c in REGIONS]:
            if not store.exists():
                continue
            with GraphStore(store, read_only=True) as db:
                ns = NetworkService(db, UnlockService(db))
                if ns.ready:
                    rows.append(H.region_metrics(ns, code))
        me = H.append_metrics(rows)
        for r in rows:
            print(f"{r['region']:5} confirmed {r['confirmed']:>7} / {r['published']:<7} night={r['night']}")
        print(f"history: {len(sn['observations'])} SNCF observations, {len(me['observations'])} metric rows")
        return
    if a.command == "build-region":
        from .regions import REGIONS, build as build_region
        codes = (a.file or "ara").split(",")
        if codes == ["all"]:
            codes = list(REGIONS)
        bad = [c for c in codes if c not in REGIONS]
        if bad:
            sys.exit(f"unknown region {bad[0]!r}; known: {', '.join(REGIONS)}, all")
        for c in codes:
            print(c, json.dumps(build_region(c)), flush=True)
        return
    if a.command in ("bulletin", "alerts"):
        from .db import GraphStore
        from .engine.service import UnlockService
        from .network.service import NetworkService
        out = Path(a.out) if a.out else ROOT / "reports"
        with GraphStore(a.store, read_only=True) as db:
            ns = NetworkService(db, UnlockService(db))
            if a.command == "bulletin":
                from .network.bulletin import write
                for k, p in write(ns, out).items():
                    print(f"{k:5} {p}")
                return
            from .network.alerts import run_file
            if not a.file:
                sys.exit("usage: python -m unlock alerts trips.json")
            res = run_file(ns, Path(a.file), out)
        for r in res["trips"]:
            flag = " (CHANGED)" if r.get("changed") else ""
            print(f"[{r['status']}{flag}] {r.get('label') or ''} {r['from']['name']} → {r['to']['name']}: {r['message']}")
        print(f"report: {res['report']}")
        sys.exit(1 if any(r["status"] != "OK" for r in res["trips"]) else 0)
    if a.command == "mcp":
        from .agent.mcp_server import main as mcp_main
        mcp_main(a.store)
        return
    if a.command == "serve":
        store = Path(a.store)
        if not store.exists():
            from .config import NORMALIZED_DIR
            from .db import GraphStore
            from .ingest.load import import_all
            print(f"No store at {store}; building it from {NORMALIZED_DIR} …")
            with GraphStore(store) as db:
                import_all(db)
        import uvicorn
        from .api.app import create_app
        uvicorn.run(create_app(Path(a.store)), host=a.host, port=a.port, workers=1)


if __name__ == "__main__":
    main()
