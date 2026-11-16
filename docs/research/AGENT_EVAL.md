# Agent evaluation — Claude Code with vs without the UNLOCK graph

Run on 16 Nov 2026 on the entrant's Windows 10 PC with `python scripts/agent_eval.py --model sonnet`
(Claude Code CLI, model reported as `claude-sonnet-5-5`). One run per task and mode — a small, single-sample
check, not a benchmark.

* **graph**: Claude Code + `python -m unlock mcp` (read-only Relate store); only `mcp__unlock__*` tools allowed.
* **no_graph**: the same model with no tools and no MCP server, in an empty directory.

Correctness is checked automatically against ground truth computed by the deterministic engine
(`expect_numbers` / `expect_text` in the script; T3 expects the agent to *not* pick a lift).

| Task | Mode | Correct | UNLOCK tools called | Time |
|---|---|---|---|---|
| T1 | graph | ✅ | find_lift, simulate_outage | 26.4 s |
| T1 | no_graph | ❌ | — | 10.7 s |
| T2 | graph | ✅ | find_lift, find_lift | 24.5 s |
| T2 | no_graph | ❌ | — | 8.6 s |
| T3 | graph | ✅ | find_lift | 19.0 s |
| T3 | no_graph | ❌ | — | 7.0 s |
| T4 | graph | ✅ | critical_lifts, network_summary | 21.2 s |
| T4 | no_graph | ❌ | — | 8.4 s |
| T5 | graph | ✅ | plan_repairs | 20.8 s |
| T5 | no_graph | ❌ | — | 7.1 s |

**Result: 5/5 with the graph, 0/5 without.** Without the graph the model did not hallucinate — it declined each time
("I have no data on lifts…"). The graph turns a refusal into a correct, sourced answer: exact lift ids, the 21
connections lost at Juvisy, the 26 connections restored by the best two repairs, and an explicit "4 candidates,
won't guess" at Pontoise. In T2 the deterministic resolver alone abstained on the English report; the agent
re-queried `find_lift` with different wording and resolved the right lift (ASC.PMR 3574).

Transcripts (sanitised: local paths and account names removed) are in this folder: `T*-graph.jsonl`,
`T*-no_graph.jsonl`, `results.json`. Reproduce with a signed-in `claude` CLI:
`python scripts/agent_eval.py --model sonnet`.
