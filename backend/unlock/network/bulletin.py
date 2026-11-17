"""Daily accessibility bulletin for maintenance and passenger-information teams.

Everything in it is read from the Relate store through NetworkService (same numbers as the API and the UI):
which lift repairs give back the most step-free journeys, what changed since the previous lift-status
observation, lifts whose status is unknown, and PRIM passenger messages that the operators' own status data
contradicts. Output: a dict, Markdown and a self-contained printable HTML page.
"""
from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import idfm_lifts as IL


def _history(ns) -> list[dict]:
    rows = ns.db.query("""MATCH (o:LiftStatusObservation) RETURN o.observed_at AS observed_at, o.lifts AS lifts,
        o.not_available_json AS na ORDER BY observed_at""")
    return [{"observed_at": r["observed_at"], "lifts": r["lifts"], "not_available": json.loads(r["na"])} for r in rows]


def build(ns, limit: int = 12) -> dict[str, Any]:
    ov = ns.overview()
    rank = ns.rank(60)
    best, pub = ov["views"]["best"], ov["views"]["published"]
    hist = _history(ns)
    ch = IL.changes(hist[-2] if len(hist) > 1 else None, hist[-1]) if hist else None
    lab = lambda lid: ns.idfm_lifts.get(lid, {})

    def lift_row(lid):
        l = lab(lid)
        return {"lift": lid, "station": ns.stations[l["zdc"]]["name"] if l.get("zdc") in ns.stations else l.get("zdc"),
                "station_id": l.get("zdc"), "operator": l.get("operator"), "label": l.get("direction") or lid,
                "status": l.get("status"), "updated": l.get("updated"),
                "entries_per_day": ns.entries.get(l.get("zdc"))}

    repairs = [r for r in rank["repairs"] if r["kind"] in ("RATP_LIFT", "SNCF_LIFT") and r.get("state") == "UNAVAILABLE"][:limit]
    checks = [r for r in rank["repairs"] if r.get("state") == "UNKNOWN"][:limit]
    unknown = sorted((lift_row(l["id"]) for l in ns.ratp_lifts if l["status"] == "UNKNOWN"),
                     key=lambda r: -(r["entries_per_day"] or 0))
    # stations where every lift the IDFM dataset lists is out of service
    by_st: dict[str, list] = {}
    for l in ns.idfm_lifts.values():
        by_st.setdefault(l["zdc"], []).append(l["status"])
    all_out = sorted(({"station": ns.stations[s]["name"], "station_id": s, "lifts": len(v),
                       "entries_per_day": ns.entries.get(s)} for s, v in by_st.items()
                      if s in ns.stations and all(x == "UNAVAILABLE" for x in v)),
                     key=lambda r: -(r["entries_per_day"] or 0))
    corr = rank["corrections"][:limit]
    # stations with a boarding point cut off today, with every lift there that is not reported working
    states = ns.view_states("best")
    cut_st = sorted({ns.net.platforms[k]["station_id"] for k, s in states.items() if s == "CLOSED" and k in ns.net.platforms})
    cut_rows = []
    for sid in cut_st:
        lifts = [{"label": l.name, "status": ns.ss.baseline_state[l.id].value, "operator": "SNCF"}
                 for st in ns.sncf_of.get(sid, []) for l in ns.ss.lifts.values()
                 if l.station_id == st and ns.ss.baseline_state[l.id].value != "AVAILABLE"]
        lifts += [{"label": l["direction"] or l["id"], "status": l["status"], "operator": "RATP"}
                  for l in ns.ratp_lifts if l["zdc"] == sid and l["status"] != "AVAILABLE"]
        cut_rows.append({"station": ns.stations[sid]["name"], "station_id": sid, "entries_per_day": ns.entries.get(sid),
                         "lifts_not_working": lifts})
    cut_rows.sort(key=lambda r: -(r["entries_per_day"] or 0))
    rec = ov["reconciliation"]
    return {
        "format": "unlock-bulletin/1",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "region": f"{ns.region['name']} ({ns.region['network_label']})",
        "night_closure_suspected": (ns.idfm_feed or {}).get("night_closure_suspected", 0),
        "freshness": {**ns._freshness(), "prim_last_lift_update": (ov["feed"] or {}).get("last_lift_update"),
                      "prim_stale_days": (ov["feed"] or {}).get("lift_messages_stale_days")},
        "headline": {"confirmed": best["confirmed"], "published": pub["confirmed"],
                     "share": round(best["confirmed"] / pub["confirmed"], 4) if pub["confirmed"] else None,
                     "possible": best["possible"], "stations_affected": best["stations_affected"],
                     "points_closed": best["boarding_points"]["closed"], "points_doubt": best["boarding_points"]["doubt"],
                     "lifts_out": {"ratp": (ov.get("idfm_status") or {}).get("ratp_unavailable"),
                                   "sncf": sum(1 for l in ns.ss.lifts.values()
                                               if ns.ss.baseline_state.get(l.id).value == "UNAVAILABLE")}},
        "repairs": repairs,
        "checks": checks,
        "changes": None if ch is None else {
            "since": ch["since"], "observations": len(hist),
            "newly_out": [lift_row(x) for x in ch["newly_out"]],
            "back_in_service": [{**lift_row(x), "status": "AVAILABLE"} for x in ch["back_in_service"]]},
        "unknown_status": unknown,
        "stations_all_lifts_out": all_out,
        "stations_cut": cut_rows,
        "corrections": corr,
        "corrections_total": {"sncf_contradicted": rec.get("GHOST", 0) + rec.get("UNRESOLVED_STATION_ALL_WORKING", 0),
                              "ratp_contradicted": rec.get("RATP_GHOST", 0),
                              "journeys_hidden": ov["stale_messages"]["journeys_hidden"]},
        "method": ("Journeys = ordered pairs of stations joined by a step-free route (boardable platforms only, every "
                   "boarding/alighting point reachable from the street by working lifts). Repair gain = journeys "
                   "confirmed again if that one lift worked, all else equal; equal gains are ordered by the "
                   f"station's daily usage ({(ns.entries_source or {}).get('title', 'n/a')}). Lift status: SNCF hourly "
                   "feed for SNCF lifts" + (", IDFM « État des ascenseurs » for RATP lifts." if ns.ratp_lifts else ".")),
    }


def _n(x):
    return "—" if x is None else f"{x:,}".replace(",", " ")


def to_markdown(b: dict) -> str:
    h, f = b["headline"], b["freshness"]
    L = [f"# Step-free access bulletin — {b['region']}", "",
         f"Generated {b['generated_at']} · SNCF lift status {f['sncf_lift_status'] or '—'}"
         + (f" · IDFM lift status {f['idfm_lift_status']}" if f['idfm_lift_status'] else "")
         + (f" · PRIM lift messages last updated {f['prim_last_lift_update']} ({f['prim_stale_days']} days ago)"
            if f['prim_last_lift_update'] else ""), "",
         f"**{_n(h['confirmed'])} of {_n(h['published'])} published step-free journeys are confirmed today "
         f"({h['share'] * 100:.1f} %).** {_n(h['stations_affected'])} stations affected; {_n(h['points_closed'])} "
         f"boarding points cut, {_n(h['points_doubt'])} in doubt. Lifts out: "
         + (f"{_n(h['lifts_out']['ratp'])} RATP, " if h['lifts_out']['ratp'] is not None else "")
         + f"{_n(h['lifts_out']['sncf'])} SNCF.", "",
         "## Fix first", "", "| # | Station | Lift | Operator | Journeys regained | Daily users | Status updated |",
         "|---|---|---|---|---|---|---|"]
    for i, r in enumerate(b["repairs"], 1):
        L.append(f"| {i} | {r['station']} | {(r.get('name') or r['lift'])[:90]} | {r.get('operator') or 'SNCF'} | "
                 f"{_n(r['gain'])} | {_n(r.get('entries_per_day'))} | {r.get('updated') or r.get('first_reported') or '—'} |")
    if not b["repairs"]:
        L.append("| — | No single lift repair gives back a journey today. | | | | | |")
    if b.get("checks"):
        L += ["", "## Check first — status unknown, journeys at stake", "",
              "| Station | Lift | Operator | Journeys confirmed if it works | Daily users | Note |", "|---|---|---|---|---|---|"]
        for r in b["checks"]:
            note = "switched off at night" if r.get("status_note") == "NIGHT_CLOSURE_SUSPECTED" else "status unknown"
            L.append(f"| {r['station']} | {(r.get('name') or r['lift'])[:90]} | {r.get('operator') or 'SNCF'} | "
                     f"{_n(r['gain'])} | {_n(r.get('entries_per_day'))} | {note} |")
    if b["stations_cut"]:
        L += ["", "## Stations cut off today", "",
              "At least one boarding point has no step-free route to the street. Lifts not reported working:", ""]
        for r in b["stations_cut"]:
            from collections import Counter
            grp = Counter((" ".join(x["label"].split())[:70], x["operator"], x["status"].lower()) for x in r["lifts_not_working"])
            ls = "; ".join(f"{lab} ({op}, {st}{f', ×{n} lifts' if n > 1 else ''})" for (lab, op, st), n in list(grp.items())[:6])
            L.append(f"- {r['station']} — {ls or 'see station topology'}")
    c = b["changes"]
    if b.get("night_closure_suspected"):
        L.insert(4, f"> Night snapshot: {b['night_closure_suspected']} RATP lifts switched off since 23:00 (Paris) are "
                    "counted as *unknown* — end-of-service shutdown is far more likely than a breakdown. Re-run after "
                    "the morning fetch for daytime figures.\n")
    L += ["", "## Changes since the previous observation", ""]
    if not c:
        L.append("No earlier lift-status observation is stored for this region.")
    elif not c["since"]:
        L.append("First observation: changes will appear from the next lift-status fetch.")
    else:
        L.append(f"Since {c['since']}: {len(c['newly_out'])} newly out of service, {len(c['back_in_service'])} back in service.")
        for title, rows in (("Newly out", c["newly_out"]), ("Back in service", c["back_in_service"])):
            if rows:
                L += ["", f"**{title}**", ""] + [f"- {r['station']} — {r['label'][:90]} ({r['operator']})" for r in rows[:25]]
    if b["unknown_status"]:
        L += ["", "## Status unknown — check on site", ""]
        L += [f"- {r['station']} — {r['label'][:90]} (updated {r['updated'] or '—'})" for r in b["unknown_status"]]
    if b["stations_all_lifts_out"]:
        L += ["", "## Stations where every listed lift is out", ""]
        L += [f"- {r['station']} ({r['lifts']} lift{'s' if r['lifts'] > 1 else ''})" for r in b["stations_all_lifts_out"]]
    t = b["corrections_total"]
    if not b["corrections"] and not t["journeys_hidden"]:
        L += ["", "## Method", "", b["method"], ""]
        return "\n".join(L)
    L += ["", "## Passenger information to correct", "",
          f"The operators' own status data contradicts {_n(t['sncf_contradicted'])} SNCF and {_n(t['ratp_contradicted'])} "
          f"RATP lift messages still published on PRIM; together they hide {_n(t['journeys_hidden'])} step-free journeys "
          "from travellers who rely on that feed.", "", "| Station | Message | Journeys hidden | Published since |",
          "|---|---|---|---|"]
    for r in b["corrections"]:
        L.append(f"| {r['station']} | {r['text'][:90]} | {_n(r['gain'])} | {r.get('first_reported') or '—'} |")
    L += ["", "## Method", "", b["method"], ""]
    return "\n".join(L)


def to_html(b: dict) -> str:
    """Self-contained printable page (no script, no external resource)."""
    import re
    md = to_markdown(b)
    out, table = [], []

    def inline(s):
        s = html.escape(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        return re.sub(r"(?<![\w*])\*([^*]+?)\*(?![\w*])", r"<em>\1</em>", s)

    def flush():
        if table:
            head, *rows = [r for r in table if not re.match(r"^\|[-| ]+\|$", r)]
            cells = lambda r: [c.strip() for c in r.strip("|").split("|")]
            out.append("<table><thead><tr>" + "".join(f"<th scope='col'>{inline(c)}</th>" for c in cells(head)) +
                       "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in cells(r)) + "</tr>"
                                                       for r in rows) + "</tbody></table>")
            table.clear()

    in_list = False
    for line in md.splitlines():
        if line.startswith("|"):
            table.append(line)
            continue
        flush()
        if line.startswith("- "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{inline(line[2:])}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        if line.startswith("# "):
            out.append(f"<h1>{inline(line[2:])}</h1>")
        elif line.startswith("## "):
            out.append(f"<h2>{inline(line[3:])}</h2>")
        elif line.startswith("> "):
            out.append(f"<blockquote>{inline(line[2:])}</blockquote>")
        elif line.strip():
            out.append(f"<p>{inline(line)}</p>")
    flush()
    if in_list:
        out.append("</ul>")
    css = ("body{font:15px/1.5 system-ui,sans-serif;color:#1d2433;max-width:62rem;margin:2rem auto;padding:0 1rem}"
           "h1{font-size:1.6rem;margin-bottom:.2rem}h2{font-size:1.15rem;margin-top:2rem;border-bottom:2px solid #1d2433}"
           "table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;padding:4px 6px;"
           "border-bottom:1px solid #d5d9e0;vertical-align:top}th{background:#eef1f5}p:nth-of-type(1){color:#5b667a}"
           "blockquote{margin:1rem 0;padding:.6rem .9rem;border-left:4px solid #8a5600;background:#fff6e5}"
           "@media print{body{margin:0}h2{break-after:avoid}tr{break-inside:avoid}}")
    return (f"<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' "
            f"content='width=device-width,initial-scale=1'><title>UNLOCK bulletin {b['generated_at'][:10]}</title>"
            f"<style>{css}</style></head><body>{''.join(out)}</body></html>")


def write(ns, out_dir: Path) -> dict[str, Path]:
    b = build(ns)
    out_dir.mkdir(parents=True, exist_ok=True)
    day = b["generated_at"][:10]
    paths = {"json": out_dir / f"bulletin-{day}.json", "md": out_dir / f"bulletin-{day}.md",
             "html": out_dir / f"bulletin-{day}.html"}
    paths["json"].write_text(json.dumps(b, ensure_ascii=False, indent=1, default=str), encoding="utf-8", newline="\n")
    paths["md"].write_text(to_markdown(b), encoding="utf-8", newline="\n")
    paths["html"].write_text(to_html(b), encoding="utf-8", newline="\n")
    return paths
