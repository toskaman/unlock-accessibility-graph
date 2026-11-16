"""Evaluate incident -> lift resolution on data/eval/incidents.jsonl (synthetic, hand-written).

Compares the graph-grounded resolver with a plain text-search baseline that ranks lifts by word
overlap with their raw name + description (what a search box over the source CSV would do).
Writes docs/research/incident_eval.json. Usage: python scripts/eval_incidents.py [--store PATH]
"""
import argparse, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from unlock.config import ROOT, STORE_PATH  # noqa: E402
from unlock.db import GraphStore  # noqa: E402
from unlock.engine.resolve import build_index, resolve, reported_state, _tokens  # noqa: E402

ap = argparse.ArgumentParser(); ap.add_argument("--store", default=str(STORE_PATH)); a = ap.parse_args()
cases = [json.loads(l) for l in (ROOT / "data" / "eval" / "incidents.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]

def grade(expect, status, lift_id):
    if expect in ("AMBIGUOUS", "NOT_FOUND"):
        if status == "RESOLVED": return "WRONG_CONFIDENT"
        return "CORRECT"
    if status == "RESOLVED":
        return "CORRECT" if lift_id.startswith(expect) else "WRONG_CONFIDENT"
    return "ABSTAINED"

with GraphStore(a.store, read_only=True) as db:
    ix = build_index(db)
docs = [(l, set(_tokens(f"{l.station} {l.name} {l.description}"))) for ls in ix.lifts.values() for l in ls]
rows, tally = [], {"graph": {}, "text_search": {}}
for c in cases:
    r = resolve(ix, c["text"])
    top = r["lift_candidates"][0]["lift_id"] if r["lift_candidates"] else ""
    g = grade(c["expect"], r["status"], top)
    toks = set(_tokens(c["text"]))
    best = max(docs, key=lambda d: (len(toks & d[1]), d[0].lift_id))
    b = grade(c["expect"], "RESOLVED" if toks & best[1] else "NOT_FOUND", best[0].lift_id)
    st_ok = reported_state(c["text"]) == c["state"]
    rows.append({"text": c["text"], "expect": c["expect"], "graph_status": r["status"], "graph_top": top[:8],
                 "graph_grade": g, "baseline_top": best[0].lift_id[:8], "baseline_grade": b, "state_ok": st_ok})
    for k, v in (("graph", g), ("text_search", b)):
        tally[k][v] = tally[k].get(v, 0) + 1
n = len(cases)
summary = {k: {**v, "n": n, "correct_rate": round(v.get("CORRECT", 0) / n, 3)} for k, v in tally.items()}
summary["state_detection_correct"] = sum(r["state_ok"] for r in rows)
out = {"dataset": "data/eval/incidents.jsonl (22 hand-written synthetic reports, gold labels by the developer)",
       "summary": summary, "rows": rows}
(ROOT / "docs" / "research" / "incident_eval.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
for r in rows: print(f"{r['graph_grade']:16} {r['baseline_grade']:16} {r['graph_status']:9} {r['text'][:70]}")
print(json.dumps(summary, indent=1))
