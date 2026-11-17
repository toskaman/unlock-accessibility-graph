// The /api/region/* surface for the zero-install demo: precomputed tables exported from the Relate stores
// (scripts/export_static.py) + journeys, reaches and rider alerts computed in the browser with the same rules,
// each re-checked by Relate itself running as WebAssembly in a worker.
import type { Journey, OutageDetail, Reach, Reconciliation, RegionCompareRow, RegionInfo, RegionOverview, RegionRank,
  RegionStation, RegionViewName, SavedTrip, TripStatus } from "../types";
import { norm, StaticNet, type Graph } from "./engine";

export const BASE = import.meta.env.BASE_URL;           // "/unlock-accessibility-graph/" on GitHub Pages
type Views = { overview: RegionOverview; maps: Record<RegionViewName, { view: string; stations: RegionStation[] }>;
  rank: RegionRank; reconciliation: Reconciliation };
type Cards = { lift_status_source: unknown; stations: Record<string, { outages: OutageDetail[]; lifts: unknown[] }> };
type Region = { graph: Graph; net: StaticNet; views: Views; blockers: Record<string, Record<string, any[]>>; cards?: Cards };

const cache = new Map<string, Promise<Region>>();
const json = async <T,>(path: string): Promise<T> => {
  const r = await fetch(`${BASE}data/${path}`);
  if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`);
  return r.json();
};

function region(code: string): Promise<Region> {
  if (!cache.has(code)) {
    cache.set(code, Promise.all([json<Graph>(`${code}/graph.json`), json<Views>(`${code}/views.json`),
      json<Region["blockers"]>(`${code}/blockers.json`)])
      .then(([graph, views, blockers]) => ({ graph, views, blockers, net: new StaticNet(graph) })));
  }
  return cache.get(code)!;
}

// ---------------------------------------------------------------- Relate (WebAssembly) worker
let worker: Worker | null = null;
let workerRegion = "";
let seq = 0;
const pending = new Map<number, (m: { ok: boolean; result?: any; error?: string }) => void>();
export type RelateInfo = { counts: { stations: number; platforms: number; legs: number }; version: string; engine_ms: number; load_ms: number };
let relateInfo: Promise<RelateInfo> | null = null;
function call<T>(msg: object): Promise<T> {
  return new Promise((res, rej) => {
    const id = ++seq;
    pending.set(id, (m) => (m.ok ? res(m.result) : rej(new Error(m.error))));
    worker!.postMessage({ ...msg, id });
  });
}
export function relate(code: string): Promise<RelateInfo> {
  if (!worker || workerRegion !== code) {
    worker?.terminate();
    worker = new Worker(new URL("./relateWorker.ts", import.meta.url), { type: "module" });
    worker.onmessage = (ev) => { pending.get(ev.data.id)?.(ev.data); pending.delete(ev.data.id); };
    workerRegion = code;
    relateInfo = call<RelateInfo>({ op: "init", base: BASE, region: code });
  }
  return relateInfo!;
}

// ---------------------------------------------------------------- helpers mirroring service.py
function st(r: Region, i: number) {
  const s = r.graph.stations[i];
  return { id: s[0], name: s[1], lat: s[2], lon: s[3] };
}
function legOut(r: Region, view: RegionViewName, [p, q, li]: [number, number, number]) {
  const g = r.graph, n = r.net;
  const [pp, lineIdx] = g.points[p], [qp] = g.points[q];
  const line = g.lines[lineIdx];
  return {
    board: g.platforms[pp][0], alight: g.platforms[qp][0], line: line[0],
    from: g.stations[n.stationOf[p]][0], to: g.stations[n.stationOf[q]][0],
    board_name: g.platforms[pp][1], alight_name: g.platforms[qp][1],
    line_name: line[1], mode: line[2], color: line[3] || "", text_color: line[4] || "",
    from_name: g.stations[n.stationOf[p]][1], to_name: g.stations[n.stationOf[q]][1],
    board_state: n.stateOf(view, p), alight_state: n.stateOf(view, q), path: n.legPath(li),
  };
}
function blocking(r: Region, view: RegionViewName, pts: number[]) {
  const seen = new Set<string>(), out: any[] = [];
  for (const p of pts) for (const b of r.blockers[view]?.[String(p)] || []) {
    const k = b.outage || b.lift;
    if (!seen.has(k)) { seen.add(k); out.push(b); }
  }
  return out;
}
async function verify(code: string, legs: ReturnType<typeof legOut>[]) {
  if (!legs.length) return { legs: 0, verified: 0, ok: true };
  try {
    await relate(code);
    const { verified } = await call<{ verified: number }>({ op: "legs", legs: legs.map(({ from, to, board, alight, line }) => ({ from, to, board, alight, line })) });
    return { legs: legs.length, verified, ok: verified === legs.length };
  } catch {
    return { legs: legs.length, verified: 0, ok: false };
  }
}
function whyNone(r: Region, a: number, b: number) {
  for (const x of [a, b]) if (!r.net.stationPoints.has(x)) return `${r.graph.stations[x][1]} has no platform declared wheelchair-boardable in the published data.`;
  return "The two stations are not connected by boardable platforms in the published network.";
}
function idx(r: Region, id: string) {
  const i = r.net.stationIdx.get(id);
  if (i == null) throw new Error("unknown station");
  return i;
}

async function journey(code: string, a: string, b: string, view: RegionViewName): Promise<Journey> {
  const r = await region(code), n = r.net;
  const ai = idx(r, a), bi = idx(r, b);
  const u = n.usable(view);
  const res: any = { from: st(r, ai), to: st(r, bi), view };
  let legs: [number, number, number][] | null = null;
  for (const [label, usable] of [["STEP_FREE", u.conf], ["STEP_FREE_IF_LIFTS_WORK", u.poss], ["CUT_BY_OUTAGES", u.all]] as const) {
    legs = n.journey(usable, ai, bi);
    if (legs) { res.verdict = label; break; }
  }
  if (!legs) { res.verdict = "NO_STEP_FREE_ROUTE_PUBLISHED"; res.legs = []; res.reason = whyNone(r, ai, bi); }
  else res.legs = legs.map((l) => legOut(r, view, l));
  if (res.verdict !== "STEP_FREE" && legs?.length) res.blocking_outages = blocking(r, view, legs.flatMap(([p, q]) => [p, q]));
  res.verification = await verify(code, res.legs);
  return res;
}

const LABEL_WHERE = (cut: string[], unsure: string[]) => [cut.length ? `cut at ${cut.join(", ")}` : "",
  unsure.length ? `uncertain at ${unsure.join(", ")} (a lift on the way is out or its status is unknown)` : ""].filter(Boolean).join("; ");

async function tripStatus(code: string, t: SavedTrip): Promise<TripStatus> {
  const r = await region(code), n = r.net;
  const ai = n.stationIdx.get(t.from.id), bi = n.stationIdx.get(t.to.id);
  if (ai == null || bi == null) return { status: "UNKNOWN_STATION", message: `Unknown station: ${ai == null ? t.from.name : t.to.name}`, from: t.from, to: t.to };
  let usual: [number, number][];
  if (t.usual?.length) {
    usual = t.usual.map((l) => [n.byKey.get(`${l.board}|${l.line}`) ?? -1, n.byKey.get(`${l.alight}|${l.line}`) ?? -1]);
    if (usual.some(([p, q]) => p < 0 || q < 0)) return { status: "UNKNOWN_STATION", message: "The saved usual route no longer exists in this network.", from: t.from, to: t.to };
  } else {
    const legs = n.journey(n.usable("best").all, ai, bi);
    if (!legs) return { status: "NO_STEP_FREE_ROUTE", message: whyNone(r, ai, bi), from: st(r, ai), to: st(r, bi), usual: [] };
    usual = legs.map(([p, q]) => [p, q]);
  }
  const bad = usual.flatMap(([p, q]) => [p, q]).filter((p) => n.stateOf("best", p) !== "OPEN");
  const name = (p: number) => r.graph.stations[n.stationOf[p]][1];
  const cut = [...new Set(bad.filter((p) => n.stateOf("best", p) === "CLOSED").map(name))].sort();
  const unsure = [...new Set(bad.filter((p) => n.stateOf("best", p) !== "CLOSED").map(name))].filter((x) => !cut.includes(x)).sort();
  const where = LABEL_WHERE(cut, unsure);
  const usualOut = usual.map(([p, q]) => {
    const g = r.graph, [pp, li] = g.points[p], [qp] = g.points[q];
    return { board: g.platforms[pp][0], alight: g.platforms[qp][0], line: g.lines[li][0], board_name: g.platforms[pp][1],
      alight_name: g.platforms[qp][1], line_name: g.lines[li][1] };
  });
  const meta = await snapshotMeta();
  const res: TripStatus = { status: "OK", message: "Your usual route is step-free today.", from: st(r, ai), to: st(r, bi), usual: usualOut,
    observed: { sncf_lift_status: meta.lift_status[code]?.sncf ?? null, idfm_lift_status: meta.lift_status[code]?.idfm ?? null } };
  if (!bad.length) return res;
  const now = await journey(code, t.from.id, t.to.id, "best");
  const nice = (legs: Journey["legs"]) => legs.map((l) => `${l.line_name} ${l.board_name} → ${l.alight_name}`).join(" then ");
  res.usual_blocked_at = bad.map((p) => ({ station: name(p), state: n.stateOf("best", p) }));
  if (now.verdict === "STEP_FREE" || now.verdict === "STEP_FREE_IF_LIFTS_WORK") res.alternative = now.legs;
  if (now.verdict === "STEP_FREE") { res.status = "DETOUR"; res.message = `Your usual route is ${where}. Step-free alternative today: ${nice(now.legs)}.`; }
  else if (now.verdict === "STEP_FREE_IF_LIFTS_WORK") { res.status = "AT_RISK"; res.message = `Your usual route is ${where}. The only step-free route left depends on lifts whose status is uncertain: ${nice(now.legs)}.`; }
  else { res.status = "CUT"; res.message = `No step-free route today: your usual route is ${where}, and so is every other route.`; }
  res.blocking = blocking(r, "best", bad);
  return res;
}

async function reach(code: string, origin: string, view: RegionViewName): Promise<Reach> {
  const r = await region(code), n = r.net, g = r.graph;
  const oi = idx(r, origin);
  const u = n.usable(view);
  const c = n.reachSet(u.conf, oi);
  const p = new Set([...n.reachSet(u.poss, oi)].filter((x) => !c.has(x)));
  const pub = n.reachSet(u.all, oi);
  const cut = new Set([...pub].filter((x) => !c.has(x) && !p.has(x)));
  const classes: Record<string, any> = {};
  g.stations.forEach((s, i) => {
    if (i === oi) return;
    classes[s[0]] = c.has(i) ? "CONFIRMED" : p.has(i) ? "IF_LIFTS_WORK" : cut.has(i) ? "CUT" : n.stationPoints.has(i) ? "UNREACHABLE" : "NOT_BOARDABLE";
  });
  const ent = (ids: Set<number>) => Math.round([...ids].reduce((a, i) => a + (g.stations[i][4] || 0), 0));
  const res: any = { origin: st(r, oi), view, classes,
    counts: { confirmed: c.size, if_lifts_work: p.size, cut: cut.size, published: pub.size },
    entries_per_day: { confirmed: ent(c), if_lifts_work: ent(p), cut: ent(cut) }, origin_boardable: n.stationPoints.has(oi) };
  try {
    await relate(code);
    const usable = [...u.conf].map((k) => n.key[k]);
    const v = await call<{ stations: string[]; rounds: number; ms: number }>({ op: "reach", origin, usable });
    const same = v.stations.length === c.size && v.stations.every((s) => c.has(n.stationIdx.get(s)!));
    res.verification = { engine: c.size, cypher: v.stations.length, ok: same, rounds: v.rounds, ms: v.ms,
      query: "Relate (WebAssembly, in this browser): UNWIND $frontier … (s)-[:HAS_PLATFORM]->(x)-[e:LEG]->(y)<-[:HAS_PLATFORM]-(t)" };
  } catch (e) {
    res.verification = { engine: c.size, cypher: -1, ok: false, rounds: 0, ms: 0, query: `Relate could not start in this browser: ${e}` };
  }
  return res;
}

let metaP: Promise<{ exported_at: string; version: string; lift_status: Record<string, { sncf: string | null; idfm: string | null }> }> | null = null;
export const snapshotMeta = () => (metaP = metaP || json("meta.json"));

export const staticRegionApi = (code: () => string) => ({
  overview: async () => (await region(code())).views.overview,
  map: async (view: RegionViewName) => (await region(code())).views.maps[view],
  rank: async () => (await region(code())).views.rank,
  search: async (text: string) => {
    const r = await region(code()), q = norm(text);
    if (!q) return [];
    return r.graph.stations.map((s, i) => ({ s, i, nm: norm(s[1]) })).filter((x) => x.nm.includes(q))
      .sort((a, b) => Number(!a.nm.startsWith(q)) - Number(!b.nm.startsWith(q)) || a.nm.length - b.nm.length || (a.s[1] < b.s[1] ? -1 : 1))
      .slice(0, 8).map((x) => ({ id: x.s[0], name: x.s[1], boardable: r.net.stationPoints.has(x.i) }));
  },
  journey: (a: string, b: string, view: RegionViewName) => journey(code(), a, b, view),
  stationOutages: async (id: string, _view: RegionViewName) => {
    const r = await region(code());
    r.cards = r.cards || await json<Cards>(`${code()}/cards.json`);
    const c = r.cards.stations[id] || { outages: [], lifts: [] };
    const i = r.net.stationIdx.get(id)!;
    return { station: { id, name: r.graph.stations[i][1] }, outages: c.outages, lifts: c.lifts as any, lift_status_source: r.cards.lift_status_source };
  },
  reconciliation: async () => (await region(code())).views.reconciliation,
  trips: async (trips: SavedTrip[]) => ({ trips: await Promise.all(trips.map((t) => tripStatus(code(), t))) }),
  reach: (id: string, view: RegionViewName) => reach(code(), id, view),
  history: () => json<{ region: string; observations: Record<string, unknown>[] }>(`${code()}/history.json`),
  historyLifts: () => json<unknown>(`${code()}/history_lifts.json`),
  timelapse: () => json<{ region: string; frames: { t: string; night: boolean; confirmed: number; published: number; stations: Record<string, string> }[] }>(`${code()}/timelapse.json`),
});

export const staticRegions = () => json<RegionInfo[]>("regions.json");
export const staticCompare = () => json<{ regions: RegionCompareRow[] }>("compare.json");
