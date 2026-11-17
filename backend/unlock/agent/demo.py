"""The recorded agent sessions (docs/research/agent_demo/runs.json), trimmed for the web app's replay panel.

Nothing is rewritten: questions, tool calls, tool results (cut to a readable length) and answers are as recorded.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..config import ROOT

RUNS = ROOT / "docs" / "research" / "agent_demo" / "runs.json"
ORDER = ["rider", "shared_rider", "shared_maintenance", "maintenance"]


def load(path: Path = RUNS, max_result: int = 700) -> dict[str, Any]:
    if not path.exists():
        return {"sessions": []}
    runs = {r["id"]: r for r in json.loads(path.read_text(encoding="utf-8"))}
    out = []
    for rid in [x for x in ORDER if x in runs] + [x for x in runs if x not in ORDER]:
        r = runs[rid]
        out.append({"id": rid, "who": r["who"], "prompt": r["prompt"], "model": r.get("model"), "seconds": r.get("seconds"),
                    # ToolSearch is Claude Code loading the tools' schemas, not a question to the graph (kept in the raw file)
                    "calls": [{"name": c["name"], "input": c.get("input", {}),
                               "result": (c.get("result") or "")[:max_result],
                               "truncated": len(c.get("result") or "") > max_result} for c in r.get("calls", [])
                              if c["name"] != "ToolSearch"],
                    "answer": r.get("answer", "")})
    return {"source": "docs/research/agent_demo/runs.json", "sessions": out}
