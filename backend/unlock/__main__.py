"""UNLOCK command line.

  python -m unlock fetch        download official source snapshots (data/raw)
  python -m unlock normalize    build data/normalized/graph_input.json
  python -m unlock import       import into the Relate store (idempotent)
  python -m unlock build        normalize + import
  python -m unlock serve        run the API (+ built frontend) on 127.0.0.1:8000
  python -m unlock stats        print graph counts from the store
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
    ap.add_argument("command", choices=["fetch", "normalize", "import", "build", "serve", "stats"])
    ap.add_argument("--store", default=str(STORE_PATH))
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-gtfs", action="store_true")
    a = ap.parse_args()

    if a.command == "fetch":
        subprocess.run([sys.executable, str(ROOT / "scripts" / "fetch_sources.py")], check=True)
    if a.command in ("normalize", "build"):
        from .ingest.normalize import build
        rep = build(with_gtfs=not a.no_gtfs)
        print(json.dumps(rep["counts"], indent=1))
    if a.command in ("import", "build"):
        from .db import GraphStore
        from .ingest.load import run_import
        with GraphStore(a.store) as db:
            print(json.dumps(run_import(db)["after"], indent=1))
    if a.command == "stats":
        from .db import GraphStore
        with GraphStore(a.store, read_only=True) as db:
            print(json.dumps(db.counts(), indent=1))
    if a.command == "serve":
        import uvicorn
        from .api.app import create_app
        uvicorn.run(create_app(Path(a.store)), host=a.host, port=a.port, workers=1)


if __name__ == "__main__":
    main()
