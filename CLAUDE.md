# Notes for coding agents working on UNLOCK

- Python package lives in `backend/unlock`; run with `PYTHONPATH=backend` or after `pip install -e .`.
- The Relate store is single-writer and thread-affine. Always go through `unlock.db.GraphStore`; never open
  `relate.connect` on another thread or a second writable connection while the server runs.
- Never modify `StatusSnapshot` nodes; scenarios only add `OVERRIDES` relationships.
- Every derived relationship must carry a `derivation` label; never link an unmatched token.
- Do not show numbers in the UI that are not returned by the API/engine.
- Tests: `pytest` (must stay green), `cd frontend && npx playwright test` (uses a store copy).
- Data refresh changes demo numbers: update DEMO_SCRIPT.md and README after `python -m unlock fetch`.
- Do not push, publish or submit without the entrant's explicit authorisation.
- Region layer: `backend/unlock/network/` (GTFS network, PRIM outages, three views). The PRIM token comes only from
  `UNLOCK_PRIM_KEY` / `UNLOCK_PRIM_KEY_FILE`; never write it to the repo, logs, the graph or test fixtures.
- A listed outage without station topology is DOUBT, never CLOSED. Don't trust the feed's own line links.
- Agent eval runs Claude Code headless with `--model sonnet` and the MCP server on a read-only store.
