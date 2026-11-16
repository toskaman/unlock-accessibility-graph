"""The single, controlled access layer to the Relate store.

Relate connections are thread-affine (``relate.threadsafety == 1``) and a
file-backed store admits exactly one writable open. ``GraphStore`` therefore
owns its connection on one dedicated worker thread; every query — from the
importer, the API or tests — is submitted to that thread and executed there.
Writes are serialised by construction. All statements are parameterised.
"""
from __future__ import annotations

import shutil
import threading
import time
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import relate

from .config import BACKUP_DIR, STORE_PATH


def _plain(v: Any) -> Any:
    """Convert Relate rich values into JSON-ready Python values."""
    if isinstance(v, relate.Node):
        return {"_kind": "node", "element_id": v.element_id, "labels": list(v.labels), **{k: _plain(x) for k, x in v.properties.items()}}
    if isinstance(v, relate.Relationship):
        return {"_kind": "rel", "element_id": v.element_id, "type": v.type, **{k: _plain(x) for k, x in v.properties.items()}}
    if isinstance(v, relate.Path):
        return {"_kind": "path", "nodes": [_plain(n) for n in v.nodes], "relationships": [_plain(r) for r in v.relationships]}
    if isinstance(v, list):
        return [_plain(x) for x in v]
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items()}
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, (relate.Temporal, relate.Duration)):
        return str(v)
    return v


class GraphStore:
    """Owns one Relate connection on a dedicated thread."""

    def __init__(self, path: Path | str = STORE_PATH, read_only: bool = False):
        self.path = Path(path) if str(path) != ":memory:" else path
        self.read_only = read_only
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="relate-owner")
        self._conn: relate.Connection | None = None
        self._lock = threading.Lock()
        self._log: deque = deque(maxlen=200)
        self._submit(self._open).result()

    # --- lifecycle -------------------------------------------------------
    def _open(self) -> None:
        if isinstance(self.path, Path):
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = relate.connect(str(self.path), read_only=self.read_only)

    def _submit(self, fn: Callable[[], Any]) -> Future:
        return self._pool.submit(fn)

    def close(self) -> None:
        def _close():
            if self._conn is not None:
                self._conn.close()
                self._conn = None
        try:
            self._submit(_close).result()
        finally:
            self._pool.shutdown(wait=True)

    def __enter__(self) -> "GraphStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # --- queries ---------------------------------------------------------
    def query(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Run one auto-committed statement on the owner thread; rows as plain dicts."""
        def _run():
            t = time.perf_counter()
            cur = self._conn.execute(cypher, params or {})
            rows = [{k: _plain(v) for k, v in row.items()} for row in cur.fetchall()]
            self._record(cypher, params, len(rows), t)
            return rows
        return self._submit(_run).result()

    def _record(self, cypher: str, params: dict | None, n: int, t0: float) -> None:
        keys = sorted((params or {}).keys())
        self._log.append({"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                          "cypher": " ".join(cypher.split())[:600], "param_keys": keys, "rows": n,
                          "ms": round((time.perf_counter() - t0) * 1000, 2)})

    def recent(self, limit: int = 30) -> list[dict]:
        return list(self._log)[-limit:][::-1]

    def query_with_summary(self, cypher: str, params: dict[str, Any] | None = None) -> tuple[list[dict], dict]:
        def _run():
            cur = self._conn.execute(cypher, params or {})
            rows = [{k: _plain(v) for k, v in row.items()} for row in cur.fetchall()]
            s = cur.consume()
            return rows, {"elapsed_ms": s.elapsed_ms, "query_type": s.query_type, "counters": dict(s.counters) if s.counters else {}}
        return self._submit(_run).result()

    def transaction(self, statements: list[tuple[str, dict[str, Any]]]) -> str | None:
        """Run several statements atomically; returns the commit bookmark."""
        def _run():
            c = self._conn
            c.autocommit = False
            try:
                for cy, p in statements:
                    t = time.perf_counter()
                    c.execute(cy, p)
                    self._record(cy, p, 0, t)
                bm = c.commit()
            except Exception:
                c.rollback()
                raise
            finally:
                c.autocommit = True
            return bm
        with self._lock:
            return self._submit(_run).result()

    def counts(self) -> dict[str, int]:
        rows = self.query("MATCH (n) RETURN labels(n)[0] AS label, count(*) AS c ORDER BY label")
        rels = self.query("MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS c ORDER BY type")
        return {"nodes": {r["label"]: r["c"] for r in rows}, "relationships": {r["type"]: r["c"] for r in rels}}


def backup(store: Path = STORE_PATH, dest_dir: Path = BACKUP_DIR) -> Path | None:
    """Copy a *closed* single-file store to a timestamped backup."""
    if not store.exists():
        return None
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = dest_dir / f"{store.stem}-{stamp}{store.suffix}"
    shutil.copy2(store, dest)
    return dest
