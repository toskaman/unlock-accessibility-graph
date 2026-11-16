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

## Region layer (v0.5.0, 17 Nov 2026) — T6–T8

Same harness, same model, new MCP tools (`check_journey`, `step_free_reach`, `region_overview`, …). The checks were
written before the runs; ground truth from the engine.

| Task | Question | Check | Round 1 graph | Round 2 graph | no_graph |
|---|---|---|---|---|---|
| T6 | Rosa Parks → Juvisy step-free now? Which lines? | mentions Neuilly, lines E and C | ✅ `check_journey` | — | ❌ (declined: no live data) |
| T7 | Reach from La Croix de Berny, and why so few? | **30** and names Viroflay | ❌ 30 right, cause not found | ❌ 30 right, main cause right (RER B lift at the origin, listed since 9 Oct), Viroflay not named | ❌ (declined) |
| T8 | Can I trust the PRIM lift feed? Last update? How many SNCF entries contradicted? | **235** and 9 Oct | ❌ 9 Oct and 159 + 76 given separately, never "235" | ✅ | ❌ (declined) |

**What the failures taught.** Round 1 showed two tool-output gaps, not model errors: `step_free_reach` did not say
which boarding points *at the origin* were in doubt, and `region_overview` returned the reconciliation as separate
counters. Both tools now return plain-language `why` / `key_facts` lines computed by the engine (nothing generated).
Round 2 (graph mode only, T7/T8) then answered T8 exactly and gave the right main cause for T7; T7 still fails the
strict pre-registered check because the agent did not look for the second outage (Viroflay) that isolates the T6
side. Round-1 transcripts are kept in `round1_v05/`.

**Totals, all tasks, final round:** with the graph 7/8 (T7 strict fail); without 0/8 — every no-graph answer declined
rather than invent numbers. Single runs, small sample, rubric written by the developer.
