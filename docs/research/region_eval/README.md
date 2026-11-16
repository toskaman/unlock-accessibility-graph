# Independent check of outage placement and SNCF lift matching

**What was checked.** 40 PRIM lift-outage messages (seeded random sample: 20 RATP/unknown operator, 20 SNCF
Gares & Connexions) with the line × platform nodes UNLOCK marked, and 30 messages UNLOCK matched to a single SNCF
lift (`MATCHES_LIFT`). Input: `sample.json` (outage ids refer to the 19:13 UTC feed snapshot; the 22:33 snapshot has the same lifts).

**Who checked.** A separate Claude agent that was not involved in building UNLOCK. It was told to read only
`sample.json` (no code, no docs) and to be strict. Its raw labels are in `labels.json`. It is independent of the
implementation, but it is still a model, not a transit expert, and it judged from the message text alone.

## Round 1 (placement rules v1)

| Placements — lines | n | | Matches | n |
|---|---|---|---|---|
| CORRECT | 33 | | CORRECT | 29 |
| SUPERSET (right line + extras) | 2 | | PLAUSIBLE | 1 |
| WRONG (misses the line) | 3 | | WRONG | 0 |
| UNCLEAR (message can't tell) | 2 | | | |

Direction (metro/tram): 7 single direction correct, 5 both marked, 0 wrong.

**What it found.** The three WRONG cases (La Défense, Maisons-Laffitte, Houilles) had the same cause: UNLOCK
trusted the lines the feed itself attaches to a message, and those links are incomplete (e.g. a RER A lift
linked only to line J). **Fix:** the feed's links are no longer used. Lines come from the text when it names one,
otherwise from every line at the station (rail lines for SNCF lifts), narrowed to the lines whose trains go
towards the named direction.

## Round 2 (rules v2, only the 7 placements that changed — `sample_v2_changed.json`, `labels_v2_changed.json`)

3 CORRECT, 3 SUPERSET, 1 UNCLEAR, **0 WRONG**.

## Resulting totals on the 40-message sample (v2)

| Lines | CORRECT 34 | SUPERSET 4 | UNCLEAR 2 | WRONG 0 |
|---|---|---|---|---|

The rules now err on the side of marking an extra line (SUPERSET) rather than missing one — which makes a
platform DOUBT, never CLOSED, so it can lower *confirmed* counts but cannot invent a blocked journey.
Sample size is small (40 + 30); the rules were changed after seeing round 1, so round 2 is not a held-out test.
