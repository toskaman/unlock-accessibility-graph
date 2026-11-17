"""Record what an AI agent does with UNLOCK's graph: real Claude Code sessions (headless) whose ONLY tools are the
UNLOCK MCP server's, on a read-only Relate store. Writes docs/AGENT_DEMO.md (questions, every tool call with its
arguments and a short extract of what the graph returned, the final answer) and the raw transcripts under
docs/research/agent_demo/. Local paths, user names and addresses are scrubbed before anything is written.

    python scripts/agent_demo.py --python <venv python> --store <copy of database/unlock.rl> [--model sonnet]
"""
from __future__ import annotations

import argparse
import json
import getpass
import re
import socket
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "research" / "agent_demo"

QUESTIONS = [
    {"id": "rider", "who": "A wheelchair user, before leaving home",
     "prompt": "Je me déplace en fauteuil roulant. Mon trajet de tous les jours, c'est Rosa Parks → Juvisy. "
               "Est-ce que je peux le faire sans marche ce matin ? Si mon trajet habituel est coupé, propose-moi un "
               "détour et dis-moi quel ascenseur pose problème. Réponds en 4 lignes maximum, en français simple."},
    {"id": "maintenance", "who": "A lift-maintenance planner",
     "prompt": "I plan lift repairs for Île-de-France today. Which single lift repair gives back the most step-free "
               "journeys, how many, and is the official outage feed reliable enough to plan from? Answer in 4 lines."},
]

SCRUB = [(re.compile(r"[A-Za-z]:\\\\?[^\s\"']*", re.I), "<path>"), (re.compile(r"\\\\\\\\[^\s\"']+"), "<path>"),
         (re.compile(r"/(home|Users|sessions|mnt)/[^\s\"']*"), "<path>"),
         (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "<ip>"), (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "<email>"),
         *[(re.compile(re.escape(n), re.I), "<user>") for n in {getpass.getuser(), socket.gethostname()} if len(n) > 2]]


def scrub(s: str) -> str:
    for rx, rep in SCRUB:
        s = rx.sub(rep, s)
    return s


def scrub_obj(o):
    if isinstance(o, str):
        return scrub(o)
    if isinstance(o, list):
        return [scrub_obj(x) for x in o]
    if isinstance(o, dict):
        return {k: scrub_obj(v) for k, v in o.items()}
    return o


def run(q: dict, python: str, store: str, model: str | None) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        cfg = {"mcpServers": {"unlock": {"command": python, "args": ["-m", "unlock", "mcp", "--store", store],
                                         "env": {"PYTHONPATH": str(ROOT / "backend"), "PYTHONIOENCODING": "utf-8"}}}}
        Path(tmp, "mcp.json").write_text(json.dumps(cfg), encoding="utf-8")
        # --setting-sources project: the entrant's own Claude Code plugins and hooks stay out of the recording
        cmd = ["claude", "-p", q["prompt"], "--output-format", "stream-json", "--verbose", "--strict-mcp-config",
               "--setting-sources", "project",
               "--mcp-config", str(Path(tmp, "mcp.json")), "--allowedTools", "mcp__unlock"]
        if model:
            cmd += ["--model", model]
        t = time.time()
        import os
        env = {**os.environ, "MCP_TIMEOUT": "180000", "MCP_TOOL_TIMEOUT": "300000"}   # the server loads the graph first
        p = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, encoding="utf-8", timeout=900, env=env)
    events = [json.loads(l) for l in p.stdout.splitlines() if l.startswith("{")]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{q['id']}.jsonl").write_text("\n".join(json.dumps(scrub_obj(e), ensure_ascii=False) for e in events),
                                          encoding="utf-8", newline="\n")
    calls, results = [], {}
    for e in events:
        m = e.get("message")
        content = m.get("content") if isinstance(m, dict) else None
        for c in content if isinstance(content, list) else []:
            if not isinstance(c, dict):
                continue
            if c.get("type") == "tool_use":
                calls.append({"id": c["id"], "name": c["name"].replace("mcp__unlock__", ""), "input": c.get("input", {})})
            elif c.get("type") == "tool_result":
                body = c.get("content")
                if isinstance(body, list):
                    body = " ".join(x.get("text", "") for x in body if isinstance(x, dict))
                results[c.get("tool_use_id")] = str(body)
    final = next((e for e in reversed(events) if e.get("type") == "result"), {})
    ini = next((e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), {})
    mcp_status = next((s.get("status") for s in ini.get("mcp_servers", []) if s.get("name") == "unlock"), None)
    return {**q, "seconds": round(time.time() - t, 1), "model": ini.get("model") or model, "mcp_status": mcp_status,
            "calls": [{**c, "result": results.get(c["id"], "")} for c in calls],
            "answer": final.get("result", ""), "cost_usd": final.get("total_cost_usd")}


def render(runs: list[dict]) -> str:
    L = ["# Ask an agent — UNLOCK's graph as tools for an AI agent", "",
         f"Recorded {datetime.now(timezone.utc).strftime('%d %b %Y %H:%M UTC')} with Claude Code (headless) whose **only** "
         "tools are the UNLOCK MCP server's, on a read-only copy of the Relate store loaded with that morning's lift "
         "status. Nothing below is edited except local paths. Raw transcripts: `docs/research/agent_demo/`. "
         "Reproduce: `python scripts/agent_demo.py --python <venv python> --store <copy of database/unlock.rl>`.", "",
         "Why it matters: without the graph the same model can only guess (0 of 8 checked answers right in "
         "[AGENT_EVAL.md](research/AGENT_EVAL.md)); with it, every number in the answer comes from a tool call that "
         "read the graph.", ""]
    for r in runs:
        L += [f"## {r['who']}", "", f"> {r['prompt']}", "", f"**Tool calls ({len(r['calls'])})** — read in order:", ""]
        for i, c in enumerate(r["calls"], 1):
            args = json.dumps(c["input"], ensure_ascii=False)
            res = re.sub(r"\s+", " ", c["result"])[:260]
            L += [f"{i}. `{c['name']}({args[1:-1] if args != '{}' else ''})`", f"   ↳ {scrub(res)}{'…' if len(c['result']) > 260 else ''}"]
        L += ["", "**Answer**", "", scrub(r["answer"]).strip(), "",
              f"*{r['seconds']} s" + (f", model {r['model']}" if r.get("model") else "") + ".*", ""]
    L += ["## In the video (15 s)", "",
          "Terminal on the left, UNLOCK on the right. Type the rider's question into `claude` (with the UNLOCK MCP "
          "server configured, see README › *AI agents*); let the tool calls scroll (`usual_trip_alert` …); show the "
          "answer, then the same trip in *My usual trips* — the same graph, the same answer.", ""]
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--python", required=True)
    ap.add_argument("--store", required=True)
    ap.add_argument("--model", default="sonnet")
    a = ap.parse_args()
    runs = [run(q, a.python, a.store, a.model) for q in QUESTIONS]
    (OUT / "runs.json").write_text(json.dumps(scrub_obj(runs), ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    init = [r.get("mcp_status") for r in runs]
    if any(s != "connected" for s in init):
        print("MCP server status:", init)
    (ROOT / "docs" / "AGENT_DEMO.md").write_text(render(runs), encoding="utf-8", newline="\n")
    for r in runs:
        print(r["id"], len(r["calls"]), "calls", r["seconds"], "s:", r["answer"][:200].replace("\n", " "))


if __name__ == "__main__":
    main()
