"""Run real agent sessions (Claude Code, headless) WITH and WITHOUT the UNLOCK MCP tools.

Each task is a planner's question. The same model answers twice:
  * graph: Claude Code + UNLOCK MCP server (read-only Relate store), only `mcp__unlock__*` tools allowed;
  * no_graph: Claude Code with no tools at all (what a chatbot alone would say).
Transcripts (stream-json, incl. every tool call) go to docs/research/agent_eval/<task>-<mode>.jsonl and the
answers are checked against ground truth computed by the deterministic engine (`expect_numbers`).

Requires the `claude` CLI signed in. Usage:
  python scripts/agent_eval.py --python <venv python> --store database/unlock.rl [--only T1 T3]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "research" / "agent_eval"

TASKS = [
    {"id": "T1", "prompt": "Message reçu ce matin d'un agent de gare : « Juvisy : ascenseur quai 50/51 HS depuis ce matin ». "
                           "Quel est l'impact sur les correspondances accessibles sans marche, et quelle réparation "
                           "faut-il prioriser dans toute l'Île-de-France si cette panne est confirmée ? Réponds en 5 lignes max.",
     "expect_numbers": ["21"], "expect_text": ["ASC3", "Mantes"]},
    {"id": "T2", "prompt": "Report from a traveller: 'Mantes-la-Jolie: the lift between the bus station car park and the "
                           "footbridge is broken.' Which lift is it exactly, and how many confirmed step-free connections "
                           "does its outage cut? Answer in 3 lines.",
     "expect_numbers": ["5"], "expect_text": ["3574"]},
    {"id": "T3", "prompt": "Report: 'Ascenseur en panne à Pontoise'. Which lift is it and what is the impact? Answer in 3 lines.",
     "expect_numbers": [], "expect_text": [], "expect_abstain": True},
    {"id": "T4", "prompt": "Which lift in Île-de-France SNCF stations is the biggest single point of failure today, and how "
                           "many confirmed step-free connections would its failure cut? Answer in 3 lines.",
     "expect_numbers": ["21"], "expect_text": ["Juvisy"]},
    {"id": "T5", "prompt": "We can repair only two lifts this week across Île-de-France SNCF stations. Which two, and how many "
                           "confirmed step-free connections do they restore together? Answer in 3 lines.",
     "expect_numbers": ["26"], "expect_text": ["Mantes", "Noisy"]},
    # ---- region layer (v0.5.0)
    {"id": "T6", "prompt": "Can a wheelchair user travel step-free from Rosa Parks to Juvisy right now? If yes, which lines "
                           "and where do they change? Answer in 3 lines.",
     "expect_numbers": [], "expect_text": ["Neuilly"], "expect_regex": [r"\bE\b", r"\bC\b"]},
    {"id": "T7", "prompt": "From La Croix de Berny, how many stations of the Île-de-France rail/metro/tram network can a "
                           "wheelchair user reach with confirmed step-free access right now, and why so few? Answer in 4 lines.",
     "expect_numbers": ["30"], "expect_text": ["Viroflay"]},
    {"id": "T8", "prompt": "Can I trust the regional (PRIM) lift-outage feed today? When were its lift messages last updated, "
                           "and how many of the SNCF lifts it lists as broken does SNCF itself report as working? Answer in 3 lines.",
     "expect_numbers": ["235"], "expect_text": [], "expect_regex": [r"(9 oct|2026-10-09|9 october|october 9|09/10/2026|9th of october|oct(ober)? 9)"]},
]

ABSTAIN = re.compile(r"(ambigu|which (one|lift)|lequel|laquelle|préciser|preciser|clarif|several|plusieurs|cannot determine|"
                     r"can't determine|pas possible de déterminer|need more|besoin de)", re.I)


def run(task: dict, mode: str, python: str, store: str, cwd: Path, model: str | None) -> dict:
    cmd = ["claude", "-p", task["prompt"], "--output-format", "stream-json", "--verbose", "--strict-mcp-config"]
    if model:
        cmd += ["--model", model]
    if mode == "graph":
        cfg = {"mcpServers": {"unlock": {"command": python, "args": ["-m", "unlock", "mcp", "--store", store],
                                         "env": {"PYTHONPATH": str(ROOT / "backend")}}}}
        cfg_path = cwd / "mcp.json"
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
        cmd += ["--mcp-config", str(cfg_path), "--allowedTools", "mcp__unlock"]
    else:
        cmd += ["--mcp-config", json.dumps({"mcpServers": {}}), "--disallowedTools",
                "Bash Read Write Edit Glob Grep WebSearch WebFetch Task NotebookEdit TodoWrite"]
    t = time.time()
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", timeout=600)
    lines = [l for l in p.stdout.splitlines() if l.strip()]
    (OUT / f"{task['id']}-{mode}.jsonl").write_text("\n".join(lines), encoding="utf-8")
    events = [json.loads(l) for l in lines if l.startswith("{")]
    result = next((e for e in reversed(events) if e.get("type") == "result"), {})
    answer = result.get("result", "") or ""
    tools = [c.get("name") for e in events if e.get("type") == "assistant"
             for c in e.get("message", {}).get("content", []) if c.get("type") == "tool_use"]
    nums_ok = all(re.search(rf"(?<![\d.]){re.escape(n)}(?![\d])", answer) for n in task["expect_numbers"])
    text_ok = all(x.lower() in answer.lower() for x in task["expect_text"]) and \
        all(re.search(rx, answer, re.I) for rx in task.get("expect_regex", []))
    abstain_ok = bool(ABSTAIN.search(answer)) if task.get("expect_abstain") else None
    correct = (abstain_ok if task.get("expect_abstain") else (nums_ok and text_ok))
    return {"task": task["id"], "mode": mode, "seconds": round(time.time() - t, 1), "tool_calls": tools,
            "answer": answer.strip(), "correct": bool(correct), "num_turns": result.get("num_turns"),
            "exit_code": p.returncode, "stderr_tail": p.stderr[-400:]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--store", default=str(ROOT / "database" / "unlock.rl"))
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--modes", nargs="*", default=["graph", "no_graph"])
    ap.add_argument("--model", default=None)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="unlock-agent-"))   # empty dir: the agent cannot read the repo
    results_path = OUT / "results.json"
    results = json.loads(results_path.read_text(encoding="utf-8")) if results_path.exists() else []
    for task in TASKS:
        if a.only and task["id"] not in a.only:
            continue
        for mode in a.modes:
            r = run(task, mode, a.python, str(Path(a.store).resolve()), work, a.model)
            results = [x for x in results if not (x["task"] == r["task"] and x["mode"] == r["mode"])] + [r]
            print(f"{r['task']} {r['mode']:8} correct={r['correct']} tools={len(r['tool_calls'])} {r['seconds']}s :: {r['answer'][:160]!r}", flush=True)
            results_path.write_text(json.dumps(sorted(results, key=lambda x: (x["task"], x["mode"])), indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
