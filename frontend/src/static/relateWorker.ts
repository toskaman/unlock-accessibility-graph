/// <reference lib="webworker" />
// Relate (WebAssembly) in a dedicated worker: the region graph exported from the Relate store is loaded into an
// in-memory Relate database, and the static demo re-derives reaches and journey legs here with the same Cypher
// statements the server runs (backend/unlock/network/service.py: Q_REACH_STEP, verify_legs).
import type { Graph } from "./engine";

type Req = { id: number; op: "init"; base: string; region: string }
  | { id: number; op: "reach"; origin: string; usable: string[] }
  | { id: number; op: "legs"; legs: { from: string; to: string; board: string; alight: string; line: string }[] };

let db: { execute(q: string, p?: string | null): string } | null = null;
let ready: Promise<unknown> | null = null;

const Q_REACH_STEP = `UNWIND $frontier AS sid
MATCH (s:NStation {id: sid})-[:HAS_PLATFORM]->(x:NPlatform)-[e:LEG]->(y:NPlatform)<-[:HAS_PLATFORM]-(t:NStation)
WHERE (x.id + '|' + e.line) IN $usable AND (y.id + '|' + e.line) IN $usable
RETURN DISTINCT t.id AS id`;
const Q_LEGS = `UNWIND $legs AS l
MATCH (s1:NStation {id: l.from})-[:HAS_PLATFORM]->(x:NPlatform {id: l.board, boardable: true})
      -[e:LEG {line: l.line}]->(y:NPlatform {id: l.alight, boardable: true})<-[:HAS_PLATFORM]-(s2:NStation {id: l.to})
RETURN count(e) AS n`;

function ex(q: string, params?: unknown) {
  const r = JSON.parse(db!.execute(q, params === undefined ? null : JSON.stringify(params)));
  if (r.error) throw new Error(r.error);
  return r;
}

async function init(base: string, region: string) {
  const t0 = performance.now();
  const relate = await import(/* @vite-ignore */ new URL(`${base}relate/relate.js`, self.location.origin).href);
  await relate.default({ module_or_path: new URL(`${base}relate/relate_bg.wasm`, self.location.origin).href });
  db = new relate.RelateDb();
  const g: Graph = await (await fetch(`${base}data/${region}/graph.json`)).json();
  const tLoad = performance.now();
  const chunk = <T,>(a: T[], f: (c: T[]) => void) => { for (let i = 0; i < a.length; i += 2000) f(a.slice(i, i + 2000)); };
  ex("CREATE CONSTRAINT nstation_id IF NOT EXISTS FOR (n:NStation) REQUIRE n.id IS UNIQUE");
  ex("CREATE CONSTRAINT nplatform_id IF NOT EXISTS FOR (n:NPlatform) REQUIRE n.id IS UNIQUE");
  chunk(g.stations.map(([id, name]) => ({ id, name })), (rows) => ex("UNWIND $rows AS r CREATE (:NStation {id: r.id, name: r.name})", { rows }));
  const boardable = new Set(g.points.map(([p]) => p));
  chunk(g.platforms.map(([id, name, st], i) => ({ id, name, station: g.stations[st][0], boardable: boardable.has(i) })),
    (rows) => ex("UNWIND $rows AS r MATCH (s:NStation {id: r.station}) CREATE (s)-[:HAS_PLATFORM]->(:NPlatform {id: r.id, name: r.name, boardable: r.boardable})", { rows }));
  chunk(g.legs.map(([a, b, hops]) => ({ a: g.platforms[g.points[a][0]][0], b: g.platforms[g.points[b][0]][0], line: g.lines[g.points[a][1]][0], hops })),
    (rows) => ex("UNWIND $rows AS r MATCH (a:NPlatform {id: r.a}) MATCH (b:NPlatform {id: r.b}) CREATE (a)-[:LEG {line: r.line, hops: r.hops}]->(b)", { rows }));
  const counts = ex(`MATCH (s:NStation) WITH count(s) AS stations
    MATCH (p:NPlatform) WITH stations, count(p) AS platforms
    MATCH ()-[e:LEG]->() RETURN stations, platforms, count(e) AS legs`).rows[0];
  const v = ex("CALL dbms.components() YIELD name, versions WHERE name = 'Relate' RETURN versions[0] AS version").rows[0];
  return { counts, version: v?.version, engine_ms: Math.round(tLoad - t0), load_ms: Math.round(performance.now() - tLoad) };
}

self.onmessage = async (ev: MessageEvent<Req>) => {
  const m = ev.data;
  try {
    if (m.op === "init") {
      ready = ready || init(m.base, m.region);
      self.postMessage({ id: m.id, ok: true, result: await ready });
      return;
    }
    await ready;
    if (m.op === "reach") {
      const t0 = performance.now();
      const seen = new Set([m.origin]);
      let frontier = [m.origin], rounds = 0;
      while (frontier.length) {
        const rows = ex(Q_REACH_STEP, { frontier, usable: m.usable }).rows as { id: string }[];
        rounds++;
        frontier = [...new Set(rows.map((r) => r.id))].filter((x) => !seen.has(x)).sort();
        frontier.forEach((x) => seen.add(x));
      }
      seen.delete(m.origin);
      self.postMessage({ id: m.id, ok: true, result: { stations: [...seen], rounds, ms: Math.round(performance.now() - t0) } });
    } else if (m.op === "legs") {
      const n = m.legs.length ? (ex(Q_LEGS, { legs: m.legs }).rows[0]?.n ?? 0) : 0;
      self.postMessage({ id: m.id, ok: true, result: { verified: n } });
    }
  } catch (e) {
    self.postMessage({ id: m.id, ok: false, error: String((e as Error)?.message || e) });
  }
};
