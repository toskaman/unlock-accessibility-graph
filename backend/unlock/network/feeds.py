"""Subscribe to a usual trip without an account: RSS and iCalendar renderings of `trip_status`.

The trip is entirely in the URL (from, to, region, optional label), so the server stores nothing. Each fetch
recomputes the status from the lift status currently loaded. RSS: one item per (day, status) — a reader shows a
new item when the status changes. iCalendar: one all-day event for today whose title is the status; calendar
apps refresh subscribed calendars on their own schedule (REFRESH-INTERVAL asks for 2 h).
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from email.utils import format_datetime
from xml.sax.saxutils import escape

LABEL = {"OK": "Step-free today", "DETOUR": "Detour needed", "AT_RISK": "At risk", "CUT": "Cut today",
         "NO_STEP_FREE_ROUTE": "No step-free route"}


def _text(t: dict) -> str:
    lines = [t["message"]]
    for b in t.get("blocking", [])[:6]:
        lines.append(f"- {b.get('station')}: {b.get('name') or b.get('text') or b.get('lift')} ({b.get('operator')}, "
                     f"{(b.get('state') or 'listed').lower()})")
    o = t.get("observed") or {}
    lines.append("Lift status read: " + ", ".join(f"{k.replace('_lift_status', '').upper()} {v}" for k, v in o.items() if v))
    return "\n".join(lines)


def rss(t: dict, link: str, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    title = f"{t['from']['name']} → {t['to']['name']}: {LABEL.get(t['status'], t['status'])}"
    guid = hashlib.sha256(f"{t['from']['id']}|{t['to']['id']}|{now.date()}|{t['status']}".encode()).hexdigest()[:16]
    return ("<?xml version=\"1.0\" encoding=\"utf-8\"?>\n<rss version=\"2.0\"><channel>"
            f"<title>{escape('UNLOCK — ' + t['from']['name'] + ' → ' + t['to']['name'])}</title>"
            f"<link>{escape(link)}</link><description>Is this trip step-free today? Recomputed at each fetch from the "
            "published lift status.</description><ttl>120</ttl>"
            f"<item><title>{escape(title)}</title><link>{escape(link)}</link>"
            f"<guid isPermaLink=\"false\">unlock-{guid}</guid><pubDate>{format_datetime(now)}</pubDate>"
            f"<description>{escape(_text(t))}</description></item></channel></rss>\n")


def _ics_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> str:
    """RFC 5545 §3.1: lines longer than 75 octets are folded (CRLF + one space)."""
    out, cur = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        if len(cur) + len(b) > (75 if not out else 74):
            out.append(cur.decode("utf-8"))
            cur = b""
        cur += b
    out.append(cur.decode("utf-8"))
    return "\r\n ".join(out)


def ics(t: dict, link: str, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    day = now.strftime("%Y%m%d")
    nxt = datetime.fromordinal(now.date().toordinal() + 1).strftime("%Y%m%d")
    uid = f"unlock-{hashlib.sha256((t['from']['id'] + '|' + t['to']['id'] + '|' + day).encode()).hexdigest()[:16]}@unlock"
    summary = f"{LABEL.get(t['status'], t['status'])}: {t['from']['name']} → {t['to']['name']}"
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//UNLOCK//Step-free trip alert//EN", "CALSCALE:GREGORIAN",
             "METHOD:PUBLISH", f"X-WR-CALNAME:{_ics_escape('UNLOCK ' + t['from']['name'] + ' → ' + t['to']['name'])}",
             "REFRESH-INTERVAL;VALUE=DURATION:PT2H", "X-PUBLISHED-TTL:PT2H",
             "BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{now.strftime('%Y%m%dT%H%M%SZ')}",
             f"DTSTART;VALUE=DATE:{day}", f"DTEND;VALUE=DATE:{nxt}", f"SUMMARY:{_ics_escape(summary)}",
             f"DESCRIPTION:{_ics_escape(_text(t))}", f"URL:{link}", "TRANSP:TRANSPARENT", "END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(_fold(l) for l in lines) + "\r\n"
