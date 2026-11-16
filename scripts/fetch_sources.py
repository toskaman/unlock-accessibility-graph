"""Download the official source snapshots into data/raw and record a manifest.

Usage:  python scripts/fetch_sources.py [--only KEY ...] [--skip-gtfs]
Every file gets size, sha256, retrieval time and the publisher's own
'modified' timestamp (when the portal exposes one).
"""
from __future__ import annotations

import argparse, datetime as dt, hashlib, json, sys, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from unlock.config import MANIFEST_PATH, RAW_DIR  # noqa: E402
from unlock.sources import SOURCES  # noqa: E402

MAX_BYTES = 400 * 1024 * 1024


def _get(url: str, dest: Path) -> tuple[int, str]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    h, n = hashlib.sha256(), 0
    req = urllib.request.Request(url, headers={"User-Agent": "UNLOCK-hackathon/0.1"})
    with urllib.request.urlopen(req, timeout=300) as r, open(tmp, "wb") as f:
        while chunk := r.read(1 << 20):
            n += len(chunk)
            if n > MAX_BYTES:
                raise RuntimeError(f"{url} exceeds {MAX_BYTES} bytes")
            h.update(chunk); f.write(chunk)
    tmp.replace(dest)
    return n, h.hexdigest()


def _publisher_modified(meta_url: str | None) -> str | None:
    if not meta_url:
        return None
    try:
        with urllib.request.urlopen(meta_url, timeout=60) as r:
            m = json.load(r)["metas"]["default"]
            return m.get("data_processed") or m.get("modified")
    except Exception:  # metadata is informative only
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--skip-gtfs", action="store_true")
    a = ap.parse_args()
    manifest = json.loads(MANIFEST_PATH.read_text()) if MANIFEST_PATH.exists() else {}
    for key, s in SOURCES.items():
        if a.only and key not in a.only:
            continue
        if a.skip_gtfs and key == "idfm_gtfs":
            continue
        dest = RAW_DIR / s.filename
        print(f"fetch {key} -> {dest}", flush=True)
        n, sha = _get(s.url, dest)
        manifest[key] = {
            "key": key, "title": s.title, "publisher": s.publisher, "url": s.url,
            "file": s.filename, "bytes": n, "sha256": sha,
            "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "publisher_modified": _publisher_modified(s.metadata_url),
            "licence": s.licence, "licence_url": s.licence_url, "role": s.role,
        }
        print(f"  {n} bytes sha256={sha[:12]}", flush=True)
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f"manifest -> {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
