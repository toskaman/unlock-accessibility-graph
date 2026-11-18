# Live demo: hourly refresh by GitHub Actions (not active yet)

> **Status (18 Nov 2026):** the workflow is in the repository but the two repository secrets below are not set, so it does not run. The published demo is the snapshot of 17 Nov 2026.

The zero-install demo (https://toskaman.github.io/unlock-accessibility-graph/) can be rebuilt every hour by
[`.github/workflows/live-demo.yml`](../.github/workflows/live-demo.yml), with no computer of ours involved:

1. fresh lift status: SNCF's hourly file, the PRIM outage feed, IDFM « État des ascenseurs »;
2. `python -m unlock build` and `build-region all`: every region rebuilt in Relate from the committed snapshots and
   the day's GTFS / NeTEx (cached for the day);
3. every 3 hours, `python -m unlock record`: the lift-status history (History tab, map replay) grows, and the
   history files are committed to `main` (`data: lift-status observation … (live demo)`);
4. `scripts/export_static.py` and `frontend/scripts/build-static.mjs`, a smoke test of the built page in Chromium,
   then a push to the `gh-pages` branch.

The banner of the demo says when the lift status was read.

## Keys

Two free API keys are needed. They are stored as **repository secrets**, never in the code or the logs:

| Secret | What | Where to get it |
|---|---|---|
| `UNLOCK_PRIM_KEY` | PRIM API token (lift outages feed) | prim.iledefrance-mobilites.fr → account → API token |
| `UNLOCK_IDFM_ODS_KEY` | Opendatasoft API key of data.iledefrance-mobilites.fr (« État des ascenseurs ») | data.iledefrance-mobilites.fr → account → API keys |

GitHub → repository → **Settings → Secrets and variables → Actions → New repository secret**, once per key.
Without both secrets, the scheduled run stops at its first step and publishes nothing (no partial data).

A manual run (**Actions → Live demo → Run workflow**, *publish* unticked) builds and checks everything without
publishing; it works without the keys, on the committed outage and IDFM snapshots.

## Why hourly, and why history every 3 hours

SNCF publishes its lift file every hour and IDFM several times a day, so the demo follows them. The history only
needs to bound outage durations; every 3 hours keeps the committed files small (a few MB by the end of the
hackathon) while still separating morning, afternoon and evening.
