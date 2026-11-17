import { staticCompare, staticRegionApi, staticRegions } from "./static/staticApi";
import type { Analysis, Critical, Explanation, Journey, Reach, OutageDetail, Ranking, Reconciliation, RegionOverview, RegionRank, RegionStation, RegionCompareRow, RegionInfo, RegionViewName, Resolution, SavedTrip, StationGraph, StationRow, Summary, TripStatus } from "./types";

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, { ...init, headers: { "Content-Type": "application/json", ...(init?.headers || {}) } });
  } catch {
    throw new ApiError(0, "The UNLOCK server is not reachable. Start it with `python -m unlock serve`.");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try { const j = await res.json(); detail = j.detail || j.error || detail; } catch { /* keep statusText */ }
    throw new ApiError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

const q = (o: Record<string, string | null | undefined>) => {
  const p = new URLSearchParams();
  Object.entries(o).forEach(([k, v]) => v && p.set(k, v));
  const s = p.toString();
  return s ? `?${s}` : "";
};

// Which region the /api/region/* calls address (null = the server's default region, Île-de-France)
let REGION: string | null = null;
export const setApiRegion = (code: string | null) => { REGION = code; };
const rg = (path: string) => (REGION ? `${path}${path.includes("?") ? "&" : "?"}region=${encodeURIComponent(REGION)}` : path);

export const api = {
  resolve: (text: string) => call<Resolution>("/api/incidents/resolve", { method: "POST", body: JSON.stringify({ text }) }),
  critical: () => call<Critical>("/api/network/critical-lifts?limit=15"),
  summary: () => call<Summary>("/api/network/summary"),
  stations: () => call<StationRow[]>("/api/network/stations"),
  station: (id: string, scenario?: string | null, candidate?: string | null) =>
    call<StationGraph>(`/api/network/stations/${encodeURIComponent(id)}${q({ scenario_id: scenario, candidate_lift: candidate })}`),
  lift: (id: string, scenario?: string | null) =>
    call<{ lift: any; pairs_depending: number; confirmed_now: number; would_lose_if_unavailable: number }>(`/api/network/lifts/${encodeURIComponent(id)}${q({ scenario_id: scenario })}`),
  simulate: (liftIds: string[]) =>
    call<{ scenario: { id: string; name: string }; analysis: Analysis }>("/api/scenarios/simulate-outage", {
      method: "POST", body: JSON.stringify({ lift_ids: liftIds }),
    }),
  rank: (scenario: string | null) =>
    scenario ? call<Ranking>(`/api/scenarios/${scenario}/rank-interventions?limit=30`, { method: "POST" })
             : call<Ranking>(`/api/baseline/rank-interventions?limit=30`),
  deleteScenario: (id: string) => call<void>(`/api/scenarios/${id}`, { method: "DELETE" }),
  explain: (pairId: string, scenario?: string | null, candidate?: string | null) =>
    call<Explanation>(`/api/pairs/explain${q({ pair_id: pairId, scenario_id: scenario, candidate_lift: candidate })}`),
  explainCandidate: (scenario: string, lift: string) =>
    call<{ mode: string; statements: { kind: string; text: string }[]; fluent?: string }>(
      `/api/analyst/explain-candidate${q({ scenario_id: scenario, lift_id: lift })}`),
  withCandidate: (scenario: string, lift: string) =>
    call<{ with_candidate_counts: import("./types").Counts; gain: number }>(`/api/scenarios/${scenario}/with-candidate${q({ candidate_lift: lift })}`),
  export: (scenario: string) => call<unknown>(`/api/scenarios/${scenario}/export`, { method: "POST" }),
  regions: () => call<RegionInfo[]>("/api/regions"),
  regionsCompare: () => call<{ regions: RegionCompareRow[] }>("/api/regions/compare"),
  region: {
    overview: () => call<RegionOverview>(rg("/api/region/overview")),
    map: (view: RegionViewName) => call<{ view: string; stations: RegionStation[] }>(rg(`/api/region/map?view=${view}`)),
    rank: () => call<RegionRank>(rg("/api/region/rank?limit=40")),
    search: (text: string) => call<{ id: string; name: string; boardable: boolean }[]>(rg(`/api/region/stations${q({ q: text })}`)),
    journey: (a: string, b: string, view: RegionViewName) => call<Journey>(rg(`/api/region/journey${q({ from: a, to: b, view })}`)),
    stationOutages: (id: string, view: RegionViewName) =>
      call<{ station: { id: string; name: string }; outages: OutageDetail[] }>(rg(`/api/region/stations/${encodeURIComponent(id)}/outages?view=${view}`)),
    reconciliation: () => call<Reconciliation>(rg("/api/region/reconciliation?limit=400")),
    trips: (trips: SavedTrip[]) => call<{ trips: TripStatus[] }>(rg("/api/region/trips/check"), { method: "POST",
      body: JSON.stringify({ trips: trips.map((t) => ({ label: t.label || null, from: t.from.id, to: t.to.id, usual: t.usual || null, last_status: t.last_status || null })) }) }),
    reach: (id: string, view: RegionViewName) => call<Reach>(rg(`/api/region/reach${q({ from: id, view })}`)),
    history: () => call<{ region: string; observations: Record<string, unknown>[] }>(rg("/api/region/history")),
    historyLifts: () => call<unknown>(rg("/api/region/history/lifts")),
    timelapse: () => call<{ region: string; frames: { t: string; night: boolean; confirmed: number; published: number; stations: Record<string, string> }[] }>(rg("/api/region/history/timelapse")),
  },
  queries: () => call<{ store: string; queries: { at: string; cypher: string; param_keys: string[]; rows: number; ms: number }[]; catalog: Record<string, string> }>("/api/debug/queries?limit=40"),
};

// Zero-install demo (GitHub Pages): the region surface is served from the exported snapshot, computed in the
// browser and re-checked by Relate compiled to WebAssembly. Station mode needs the installed server.
export const STATIC_DEMO = import.meta.env.VITE_STATIC === "1";
if (STATIC_DEMO) {
  (api as any).region = staticRegionApi(() => REGION || "idf");
  (api as any).regions = staticRegions;
  (api as any).regionsCompare = staticCompare;
}
export const currentRegion = () => REGION;
export const bulletinUrl = (region: string, isDefault: boolean) =>
  STATIC_DEMO ? `${import.meta.env.BASE_URL}data/${region}/bulletin.html` : `/api/region/bulletin.html${isDefault ? "" : `?region=${region}`}`;
