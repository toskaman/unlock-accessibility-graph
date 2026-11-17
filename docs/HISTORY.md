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

**Where to see it.**

- *Whole region* → **History** tab: every lift seen out of service at least once in the daytime observations,
  ranked by the share of observations it was out, with *chronic* flagged, the date it went out and — for RATP lifts —
  the time IDFM last changed its status. Click a lift to open its station.
- Under the chart of confirmed journeys (best view): **Replay on the map** steps through the observations and
  recolours the map with the stations cut or in doubt at each one (*daytime only* by default; slower with reduced
  motion). *Back to now* restores today's map.
- API: `GET /api/region/history`, `/api/region/history/lifts`, `/api/region/history/timelapse`. The zero-install demo
  ships the same three files, re-exported at every collection, so it shows the history collected so far.

Night observations (between 23:00 and 06:00 Paris) are left out of the lift ranking: lifts switched off at the end of
service would otherwise look like outages.

**Limits.** Two observations a day bound durations to half a day; SNCF's file has no per-lift timestamp; an outage
that starts and ends between two fetches is never seen.
