# Lift-status history

A snapshot says which lifts are out *now*. A history says how long outages last, which lifts are out again and
again, and how many step-free journeys a region loses day after day. Nobody publishes that; UNLOCK records it.

**What is recorded** (`python -m unlock record`, run at the end of every `refresh`):

| File | One entry per | Content |
|---|---|---|
| `data/normalized/history/sncf_lift_status.json` | version of SNCF's hourly lift-status file | every lift of France not available (KO / unknown) — absent = working |
| `data/normalized/idfm_lift_history.json` | IDFM fetch | every IDF lift not available, with IDFM's update time (night switch-offs as unknown) |
| `data/normalized/history/metrics.json` | region × observation | published / confirmed / possible journeys, points cut or in doubt, lifts out, and every station not fully open (for a time-lapse map) |

**How it is collected.** Twice a day in the daytime (≈ 10:45 and 18:45 Paris) from 17 Nov 2026 to the submission
deadline — semi-automatically: a reminder scheduled in Claude triggers the refresh on the entrant's PC and commits
the history files; nothing is installed as a system task. Each commit is titled `data: lift-status observation …`.

**Analyses** (`backend/unlock/history.py`): outage spells per lift (start, end bounded by the observation times,
still out), share of observations out (chronic ≥ 30 % over ≥ 7 days), confirmed journeys per region over time.
`history.summary()` says how much history exists before drawing any conclusion.

**Limits.** Two observations a day bound durations to half a day; SNCF's file has no per-lift timestamp; an outage
that starts and ends between two fetches is never seen.
