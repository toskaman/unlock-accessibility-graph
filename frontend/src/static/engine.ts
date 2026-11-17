// Port of backend/unlock/network/engine.py + the journey/trip parts of service.py for the static demo.
// Same rules, same tie-breaking (least cost = stops ridden + 8 per boarding; ties by point id).
// The numbers it produces are checked against the server's in scripts/check_static_engine.mjs.

export type Graph = {
  format: string;
  region: { code: string; name: string; network_label: string; center: [number, number]; zoom: number };
  stations: [string, string, number, number, number | null][];      // id, name, lat, lon, entries/day
  platforms: [string, string, number, number, number][];             // id, name, station index, lat, lon
  lines: [string, string, string, string | null, string | null][];   // id, short name, mode, colour, text colour
  points: [number, number][];                                        // platform index, line index (boardable)
  legs: [number, number, number, number][];                          // from point, to point, hops, pattern
  patterns: [number, number[]][];                                    // line index, platform indices in order
  states: Record<"best" | "feed" | "published", Record<string, "OPEN" | "DOUBT" | "CLOSED">>;
  transfer_penalty: number;
};
export type PointState = "OPEN" | "DOUBT" | "CLOSED";

export class StaticNet {
  g: Graph;
  key: string[];                                   // point index → "platform|line"
  stationOf: number[];                             // point index → station index
  stationPoints = new Map<number, number[]>();     // station index → point indices, sorted by key
  out = new Map<number, [number, number, number][]>(); // point → [to point, hops, leg index], sorted by (key, line)
  byKey = new Map<string, number>();
  stationIdx = new Map<string, number>();

  constructor(g: Graph) {
    this.g = g;
    this.key = g.points.map(([p, l]) => `${g.platforms[p][0]}|${g.lines[l][0]}`);
    this.stationOf = g.points.map(([p]) => g.platforms[p][2]);
    this.key.forEach((k, i) => this.byKey.set(k, i));
    g.stations.forEach((s, i) => this.stationIdx.set(s[0], i));
    this.stationOf.forEach((s, i) => {
      const a = this.stationPoints.get(s) || [];
      a.push(i);
      this.stationPoints.set(s, a);
    });
    for (const a of this.stationPoints.values()) a.sort((x, y) => cmp(this.key[x], this.key[y]));
    g.legs.forEach(([a, b, hops], i) => {
      const o = this.out.get(a) || [];
      o.push([b, hops, i]);
      this.out.set(a, o);
    });
    for (const o of this.out.values()) o.sort((x, y) => cmp(this.key[x[0]], this.key[y[0]]) || cmp(this.lineOf(x[0]), this.lineOf(y[0])));
  }
  lineOf(p: number) { return this.g.lines[this.g.points[p][1]][0]; }
  stateOf(view: "best" | "feed" | "published", p: number): PointState { return this.g.states[view][String(p)] || "OPEN"; }
  usable(view: "best" | "feed" | "published"): { conf: Set<number>; poss: Set<number>; all: Set<number> } {
    const conf = new Set<number>(), poss = new Set<number>(), all = new Set<number>();
    this.key.forEach((_, p) => {
      all.add(p);
      const s = this.stateOf(view, p);
      if (s === "OPEN") conf.add(p);
      if (s !== "CLOSED") poss.add(p);
    });
    return { conf, poss, all };
  }

  /** Least-cost step-free journey (engine.journey). Returns legs as [board point, alight point, leg index]. */
  journey(usable: Set<number>, a: number, b: number): [number, number, number][] | null {
    if (a === b) return [];
    const start = (this.stationPoints.get(a) || []).filter((p) => usable.has(p));
    const goal = new Set((this.stationPoints.get(b) || []).filter((p) => usable.has(p)));
    if (!start.length || !goal.size) return null;
    const dist = new Map<number, number>();
    const prev = new Map<number, [number, number, number] | null>();
    const heap = new Heap<[number, string, string, number]>((x, y) => x[0] - y[0] || cmp(x[1], y[1]) || cmp(x[2], y[2]));
    for (const p of start) { dist.set(p, 0); prev.set(p, null); heap.push([0, this.key[p], "", p]); }
    let found: number | null = null;
    while (heap.size) {
      const [d, , , p] = heap.pop()!;
      if (d > (dist.get(p) ?? Infinity)) continue;
      if (goal.has(p) && prev.get(p) != null) { found = p; break; }
      for (const [q, hops, li] of this.out.get(p) || []) {
        if (!usable.has(q)) continue;
        const nd = d + this.g.transfer_penalty + (hops || 1);
        const st = this.stationOf[q];
        for (const r of [q, ...(this.stationPoints.get(st) || []).filter((x) => usable.has(x) && x !== q)]) {
          if (nd < (dist.get(r) ?? Infinity)) {
            dist.set(r, nd);
            prev.set(r, [p, li, q]);
            heap.push([nd, this.key[r], this.key[r], r]);
          }
        }
      }
    }
    if (found == null) return null;
    const legs: [number, number, number][] = [];
    let r = found;
    while (prev.get(r) != null) {
      const [p, li, q] = prev.get(r)!;
      legs.push([p, q, li]);
      r = p;
    }
    return legs.reverse();
  }

  /** Stations reachable step-free from `origin` (engine.reach_set), as station indices. */
  reachSet(usable: Set<number>, origin: number): Set<number> {
    const start = (this.stationPoints.get(origin) || []).filter((p) => usable.has(p));
    const seen = new Set(start), out = new Set<number>(), dq = [...start];
    for (let i = 0; i < dq.length; i++) {
      for (const [q] of this.out.get(dq[i]) || []) {
        if (!usable.has(q)) continue;
        const st = this.stationOf[q];
        out.add(st);
        for (const r of this.stationPoints.get(st) || []) if (usable.has(r) && !seen.has(r)) { seen.add(r); dq.push(r); }
      }
    }
    out.delete(origin);
    return out;
  }

  /** Coordinates of the stops ridden on one leg, from its stopping pattern (service.leg_path). */
  legPath(li: number): [number, number][] {
    const [a, b, , pat] = this.g.legs[li];
    const pa = this.g.points[a][0], pb = this.g.points[b][0];
    const stops = pat >= 0 ? this.g.patterns[pat][1] : [];
    const i = stops.indexOf(pa);
    const j = i >= 0 ? stops.indexOf(pb, i + 1) : -1;
    const seq = i >= 0 && j > i ? stops.slice(i, j + 1) : [pa, pb];
    return seq.map((x) => [this.g.platforms[x][4], this.g.platforms[x][3]]);
  }
}

export function cmp(a: string, b: string) { return a < b ? -1 : a > b ? 1 : 0; }

class Heap<T> {
  private a: T[] = [];
  constructor(private less: (x: T, y: T) => number) {}
  get size() { return this.a.length; }
  push(x: T) {
    const a = this.a; a.push(x);
    let i = a.length - 1;
    while (i > 0) { const p = (i - 1) >> 1; if (this.less(a[i], a[p]) >= 0) break; [a[i], a[p]] = [a[p], a[i]]; i = p; }
  }
  pop(): T | undefined {
    const a = this.a; if (!a.length) return undefined;
    const top = a[0], last = a.pop()!;
    if (a.length) {
      a[0] = last;
      let i = 0;
      for (;;) {
        const l = 2 * i + 1, r = l + 1;
        let m = i;
        if (l < a.length && this.less(a[l], a[m]) < 0) m = l;
        if (r < a.length && this.less(a[r], a[m]) < 0) m = r;
        if (m === i) break;
        [a[i], a[m]] = [a[m], a[i]]; i = m;
      }
    }
    return top;
  }
}

/** Accent- and case-insensitive name key (spaces.normalize). */
export function norm(s: string) {
  return s.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/’/g, "'").replace(/\s+/g, " ").trim();
}
