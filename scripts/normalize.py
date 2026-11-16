"""Build data/normalized/graph_input.json from data/raw (see backend/unlock/ingest/normalize.py)."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from unlock.ingest.normalize import build  # noqa: E402

t = time.time()
rep = build(with_gtfs="--no-gtfs" not in sys.argv)
print(json.dumps({k: v for k, v in rep.items() if k != "unmatched_tokens"}, indent=1, ensure_ascii=False))
print(f"normalized in {time.time()-t:.1f}s")
