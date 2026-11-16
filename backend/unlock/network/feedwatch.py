"""Feed watch: one summary line per PRIM fetch, kept in data/normalized/outage_feed_history.json.

The point is evidence over time: if the lift content of the feed is byte-for-byte the same at every observation,
the claim "the lift messages are frozen" rests on repeated observations, not on one fetch.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..config import NORMALIZED_DIR

HISTORY = NORMALIZED_DIR / "outage_feed_history.json"


def lift_content_sha(outages: list[dict]) -> str:
    rows = sorted((o["id"], o["text"], o["first_reported"] or "", o["last_update"] or "", o["messages"]) for o in outages)
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode("utf-8")).hexdigest()


def observation(doc: dict) -> dict:
    return {"observed_at": doc["observed_at"], "lifts": doc["counts"]["lifts"], "messages": doc["counts"]["messages"],
            "feed_last_lift_update": doc.get("feed_last_lift_update"),
            "feed_non_lift_last_update": doc.get("feed_non_lift_last_update"),
            "lift_content_sha": lift_content_sha(doc["outages"])}


def load(path: Path = HISTORY) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def append(doc: dict, path: Path = HISTORY) -> list[dict]:
    hist = [h for h in load(path) if h["observed_at"] != doc["observed_at"]]
    hist.append(observation(doc))
    hist.sort(key=lambda h: h["observed_at"])
    path.write_text(json.dumps(hist, indent=1, ensure_ascii=False), encoding="utf-8", newline="\n")
    return hist


def summary(hist: list[dict]) -> dict | None:
    if not hist:
        return None
    last = hist[-1]
    same = [h for h in hist if h["lift_content_sha"] == last["lift_content_sha"]]
    return {"observations": len(hist), "first_observed": hist[0]["observed_at"], "last_observed": last["observed_at"],
            "identical_lift_content": len(same), "identical_since": same[0]["observed_at"],
            "all_identical": len(same) == len(hist), "history": hist}
