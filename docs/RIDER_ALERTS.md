# Rider alerts — "is my usual trip still step-free today?"

A wheelchair user rarely plans a new journey; they repeat the same few trips. What they need is a warning
**before leaving** when one of those trips is cut, and a step-free alternative if one exists. UNLOCK answers that
from the same graph and the same lift status as the rest of the app.

## Statuses

| Status | Meaning |
|---|---|
| `OK` | Every boarding and alighting point of the usual route is reachable from the street by working lifts. |
| `DETOUR` | The usual route is blocked or uncertain somewhere, but another **confirmed** step-free route exists; it is returned. |
| `AT_RISK` | No confirmed route; one exists only if lifts whose status is uncertain (unknown, or listed out without topology) work. |
| `CUT` | No step-free route today — neither the usual one nor any other. |
| `NO_STEP_FREE_ROUTE` | Not even the published network has one (a station has no wheelchair-boardable platform). |

The message says *where* the usual route breaks — "cut at X" (a lift out with no other way, from the station
lift graph) or "uncertain at X (a lift on the way is out or its status is unknown)" — and `blocking` lists the
lifts concerned, with their source (SNCF hourly feed, IDFM *État des ascenseurs*). `observed` gives the time of
the lift-status data used: an alert is never fresher than its data.

The **usual route** is the rider's own legs if they gave them, otherwise the route UNLOCK finds on the published
network the first time the trip is checked (then stored with the trip, so a later detour is measured against it).

## Three ways to use it

**In the app** — check a journey, click *Watch …*. Trips are kept **in this browser only** (localStorage); the
server stores nothing about riders. Each time the page opens, every watched trip is re-checked, and the panel
says when a status changed since the last check.

**API** — stateless: the client sends its trips and the last status it saw.

```http
POST /api/region/trips/check            (add ?region=ara for another region)
{"trips": [{"label": "work", "from": "73798", "to": "478505", "last_status": "OK"}]}
```

`from`/`to` accept a station id or a name. Up to 20 trips per call; unknown stations come back as
`UNKNOWN_STATION`, an unknown boarding point in `usual` is a 422.

**Command line, for a daily scheduled check**

```bash
python -m unlock alerts trips.json      # exit code 1 if any trip is not OK
```

`trips.json` is `{"trips": [{"label": "...", "from": "...", "to": "..."}]}`. Each run writes the new status and
the usual route back into the file and a report `reports/alerts-<UTC time>.json`. Run it after
`python -m unlock fetch-lifts` (and the SNCF status fetch) from Windows Task Scheduler or cron; pipe the output
to whatever notifies the rider (e-mail, SMS gateway, a chat bot). UNLOCK itself sends nothing.

**AI agents** — MCP tool `usual_trip_alert(from_station, to_station)`.

## Limits

- An alert is as good as the lift-status feeds: SNCF is hourly; IDFM *État des ascenseurs* refreshes several times
  a day. PRIM's lift messages are not used for alerts (frozen since 9 Oct 2026, see the region page).
- "Step-free" covers lifts between street and platforms. It does not cover the gap between platform and train,
  boarding assistance bookings, or escalator-only paths.
- The rider's preferences (avoid a line, minimum transfer time) are not modelled.
