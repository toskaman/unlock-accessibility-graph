// Compares the browser engine (src/static/engine.ts, compiled to $ENGINE_JS) with the server engine's reference
// output ($REF, written by scripts/check_static_engine.py). Run through that script.
import fs from "node:fs";
const { StaticNet } = await import(process.env.ENGINE_JS);
const g = JSON.parse(fs.readFileSync(process.env.GRAPH, "utf8"));
const ref = JSON.parse(fs.readFileSync(process.env.REF, "utf8"));
const n = new StaticNet(g);
let bad = 0, total = 0;
for (const v of ["best", "feed"]) {
  const u = n.usable(v);
  for (const [o, [c, p]] of Object.entries(ref.reach[v])) {
    total++;
    const oi = n.stationIdx.get(o);
    const cc = n.reachSet(u.conf, oi).size, pp = n.reachSet(u.poss, oi).size;
    if (cc !== c || pp !== p) { bad++; if (bad < 5) console.log("reach diff", v, o, c, cc, p, pp); }
  }
}
let jb = 0;
for (const j of ref.journeys) {
  const u = n.usable(j.view), a = n.stationIdx.get(j.a), b = n.stationIdx.get(j.b);
  let verdict = "NO_STEP_FREE_ROUTE_PUBLISHED", legs = null;
  for (const [lab, us] of [["STEP_FREE", u.conf], ["STEP_FREE_IF_LIFTS_WORK", u.poss], ["CUT_BY_OUTAGES", u.all]]) {
    legs = n.journey(us, a, b); if (legs) { verdict = lab; break; }
  }
  const mine = (legs || []).map(([p, q]) => [g.platforms[g.points[p][0]][0], g.platforms[g.points[q][0]][0], g.lines[g.points[p][1]][0]]);
  if (verdict !== j.verdict || JSON.stringify(mine) !== JSON.stringify(j.legs)) { jb++; if (jb < 4) console.log("journey diff", j, verdict, mine); }
}
fs.writeFileSync(process.env.OUT, JSON.stringify({ reach_identical: total - bad, reach_total: total, journeys_identical: ref.journeys.length - jb, journeys_total: ref.journeys.length }, null, 1));
console.log(`reach: ${total - bad}/${total} identical; journeys: ${ref.journeys.length - jb}/${ref.journeys.length} identical (verdict + every leg)`);
