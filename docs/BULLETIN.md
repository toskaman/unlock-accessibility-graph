# Daily accessibility bulletin

One page for the teams who fix lifts and the teams who inform passengers, generated from the Relate store:

```bash
python -m unlock bulletin                                        # Île-de-France → reports/bulletin-<date>.{json,md,html}
python -m unlock bulletin --store database/regions/ara.rl        # another region
```

Also served live: `GET /api/region/bulletin` (JSON + Markdown) and `GET /api/region/bulletin.html` (printable page,
no script, no external resource) — linked from *Repairs that matter* in the app; MCP tool `maintenance_bulletin`.

## Sections

| Section | Content | Source of every number |
|---|---|---|
| Headline | Confirmed step-free journeys today vs the published network; stations affected; boarding points cut / in doubt; lifts out by operator | region views (`view_summary`) |
| Fix first | Lift repairs ranked by journeys given back; equal gains ordered by the station's daily use | `rank()` — each candidate evaluated alone, exact reachability |
| Stations cut off today | Stations with a boarding point that has no step-free route to the street, and every lift there not reported working | best view + SNCF / IDFM status |
| Changes since the previous observation | Lifts newly out of service / back in service between the last two IDFM lift-status fetches | `(:LiftStatusObservation)` nodes |
| Status unknown — check on site | RATP lifts IDFM reports as `unknown`, busiest stations first | IDFM *État des ascenseurs* |
| Stations where every listed lift is out | — | IDFM *État des ascenseurs* |
| Passenger information to correct | PRIM messages the operators' own status data contradicts, ranked by journeys they hide | reconciliation (SNCF hourly feed, IDFM status) |

## Reading it right

- **Journeys regained** counts ordered pairs of stations newly joined by a confirmed step-free route if that single
  lift worked, all else equal. A station whose only access is cut usually gives back ~2 × (stations reachable from
  it), so many repairs tie; the tie is broken by daily use (IDFM validations Q2 2026, or SNCF passengers 2025 ÷ 365
  in other regions) — a weight for *how many people* pass there, **not** a count of wheelchair users (D24, D26).
- A station that needs **two** repairs (both lifts of a quay out) gives nothing back for either repair alone; it
  appears under *Stations cut off today*, not under *Fix first*.
- "Status updated" is the time the publisher last changed the lift's record, not necessarily when it broke.
