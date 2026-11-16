"""Fetch lift outages from the PRIM traffic-information API (needs a personal PRIM token).

The token is read from ``UNLOCK_PRIM_KEY`` or from the file named by
``UNLOCK_PRIM_KEY_FILE``. It is sent only in the ``apikey`` header to
prim.iledefrance-mobilites.fr and is never written to disk, logs or the graph.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from ..config import MANIFEST_PATH, RAW_DIR
from ..sources import PRIM_LINE_REPORTS as SRC


def token() -> str:
    tok = os.environ.get("UNLOCK_PRIM_KEY", "").strip()
    path = os.environ.get("UNLOCK_PRIM_KEY_FILE", "").strip()
    if not tok and path:
        tok = Path(path).read_text(encoding="utf-8").strip()
    if not tok:
        raise SystemExit("No PRIM token: set UNLOCK_PRIM_KEY or UNLOCK_PRIM_KEY_FILE (free account on "
                         "prim.iledefrance-mobilites.fr). UNLOCK runs without it on the committed snapshot.")
    return tok


def _get(url: str, tok: str) -> dict:
    req = urllib.request.Request(url, headers={"apikey": tok, "User-Agent": "UNLOCK-hackathon/0.3"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def fetch(dest: Path | None = None, page_size: int = 100, max_pages: int = 60) -> Path:
    tok = token()
    dest = dest or RAW_DIR / SRC.filename
    pages, start = [], 0
    while start < max_pages:
        d = _get(f"{SRC.url}?count={page_size}&start_page={start}&disable_geojson=true&depth=1", tok)
        pages.append({k: d.get(k) for k in ("pagination", "disruptions", "line_reports", "feed_publishers", "context")})
        pg = d["pagination"]
        if (pg["start_page"] + 1) * pg["items_per_page"] >= pg["total_result"]:
            break
        start += 1
        time.sleep(0.2)  # stay far below the PRIM rate limit
    fetched = datetime.now(timezone.utc).isoformat(timespec="seconds")
    body = json.dumps({"fetched_at": fetched, "source": SRC.url, "pages": pages}, ensure_ascii=False).encode("utf-8")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(body)
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8")) if MANIFEST_PATH.exists() else {}
    manifest[SRC.key] = {"key": SRC.key, "title": SRC.title, "publisher": SRC.publisher, "url": SRC.url,
                         "file": SRC.filename, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
                         "retrieved_at": fetched, "publisher_modified": None, "licence": SRC.licence,
                         "licence_url": SRC.licence_url, "role": SRC.role}
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return dest
