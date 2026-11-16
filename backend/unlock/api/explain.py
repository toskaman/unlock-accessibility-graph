"""UNLOCK Analyst — explanations built only from computed results.

Default mode is fully deterministic: sentences are assembled from the structured
analysis (no model involved). If ``ANTHROPIC_API_KEY`` is set, ``rephrase()``
may ask a model to rewrite the *same facts* more fluently; the rewrite is
rejected unless every number it contains already appears in the facts, so the
model can never introduce a figure. Each statement is tagged with its kind:
OBSERVATION (source record), CALCULATION (engine), SIMULATION (scenario),
DERIVATION (text-derived topology) or UNKNOWN.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from typing import Any

CLASS_TEXT = {
    "CONFIRMED_ACCESSIBLE": "confirmed step-free",
    "CONFIRMED_BLOCKED": "blocked (no modeled step-free route)",
    "UNVERIFIED": "unverified",
    "OUT_OF_SCOPE": "out of scope (no modeled lift route)",
}


def _s(kind: str, text: str) -> dict[str, str]:
    return {"kind": kind, "text": text}


def explain_pair(d: dict[str, Any]) -> dict[str, Any]:
    p, c = d["pair"], d["classification"]
    out = [
        _s("CALCULATION", f"Between “{p['a_name']}” and “{p['b_name']}” the engine found "
                          f"{len(d['routes'])} modeled lift route(s) in the Relate graph."),
        _s("CALCULATION", f"Baseline (latest published status): {CLASS_TEXT[c['baseline']]}. "
                          f"Under this scenario: {CLASS_TEXT[c['scenario']]} ({c['reason'].replace('_', ' ').lower()})."),
    ]
    for i, r in enumerate(d["routes"], 1):
        names = ", ".join(f"{l['name'] or l['id']} [{l['state']}{' · simulated' if l['overridden'] else ''}]" for l in r["lifts"])
        out.append(_s("DERIVATION", f"Route {i} needs: {names} → route is {r['state'].lower()}."))
        for l in r["lifts"]:
            st = (l.get("evidence") or {}).get("status") or {}
            if st:
                out.append(_s("OBSERVATION", f"{l['name']}: publisher status “{st.get('raw_state')}” in snapshot "
                                             f"{st.get('snapshot_id')} (observed {st.get('observed_at')})."))
    if c.get("candidate_lift"):
        out.append(_s("SIMULATION", f"If lift {c['candidate_lift']} is restored, this pair becomes "
                                    f"{CLASS_TEXT[c['with_candidate']]}."))
    for u in d.get("unknowns", []):
        out.append(_s("UNKNOWN", u))
    return {"mode": "deterministic", "statements": out}


def explain_candidate(ranking: dict[str, Any], lift_id: str, analysis: dict[str, Any]) -> dict[str, Any]:
    cands = ranking["candidates"]
    me = next((c for c in cands if c["lift_id"] == lift_id), None)
    if me is None:
        return {"mode": "deterministic", "statements": [
            _s("CALCULATION", "This lift is not a restoration candidate in this scenario (it is already available "
                              "or no modeled pair depends on it).")]}
    st = [
        _s("SIMULATION" if me["simulated"] else "OBSERVATION",
           f"{me['lift_name']} at {me['station_name']} is {me['current_state'].lower()} "
           f"{'in this simulated scenario' if me['simulated'] else 'in the latest published status'}."),
        _s("CALCULATION", f"Restoring it changes confirmed step-free pairs by +{me['gain']} "
                          f"(rank {me['rank']} of {ranking['candidate_count']} candidates); "
                          f"{me['pairs_depending']} modeled pair(s) have at least one route through it."),
    ]
    if me["still_blocked_by_others"]:
        st.append(_s("CALCULATION", f"{len(me['still_blocked_by_others'])} other unavailable lift(s) still block "
                                    "some dependent pairs — they only pay off when repaired together."))
    others = [c for c in cands if c["lift_id"] != lift_id][:1]
    if others:
        o = others[0]
        diff = me["gain"] - o["gain"]
        st.append(_s("CALCULATION", f"Next best alternative: {o['lift_name']} at {o['station_name']} (+{o['gain']}); "
                                    f"difference {diff:+d} pair(s)."))
    st.append(_s("UNKNOWN", "Pairs count modeled platform/exit connections inside stations, not passengers; "
                            "lift→space links are derived from the publisher's location text."))
    result = {"mode": "deterministic", "statements": st}
    llm = rephrase(st)
    if llm:
        result["fluent"] = llm
        result["mode"] = "deterministic+model-rephrased"
    return result


_NUM = re.compile(r"[-+]?\d+(?:[.,]\d+)?")


def rephrase(statements: list[dict[str, str]]) -> str | None:
    """Optional: ask a model to rewrite the facts. Returns None unless safe."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    facts = "\n".join(f"[{s['kind']}] {s['text']}" for s in statements)
    body = json.dumps({
        "model": os.environ.get("UNLOCK_ANALYST_MODEL", "claude-sonnet-5-5"), "max_tokens": 400,
        "system": "Rewrite the facts below as 2-4 plain sentences for a transport accessibility planner. "
                  "Use ONLY the facts given. Do not add numbers, causes or recommendations not present. "
                  "Keep the distinction between observed, simulated and calculated statements.",
        "messages": [{"role": "user", "content": facts}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            text = "".join(b.get("text", "") for b in json.load(r).get("content", []))
    except Exception:
        return None
    allowed = set(_NUM.findall(facts))
    if not text or any(n not in allowed for n in _NUM.findall(text)):
        return None  # a number not present in the facts -> reject the rewrite
    return text.strip()
