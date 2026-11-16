import type { Analysis, Critical, Explanation, Journey, Reach, OutageDetail, Ranking, Reconciliation, RegionOverview, RegionRank, RegionStation, RegionViewName, Resolution, StationGraph, StationRow, Summary } from "./types";

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
  region: {
    overview: () => call<RegionOverview>("/api/region/overview"),
    map: (view: RegionViewName) => call<{ view: string; stations: RegionStation[] }>(`/api/region/map?view=${view}`),
    rank: () => call<RegionRank>("/api/region/rank?limit=40"),
    search: (text: string) => call<{ id: string; name: string; boardable: boolean }[]>(`/api/region/stations${q({ q: text })}`),
    journey: (a: string, b: string, view: RegionViewName) => call<Journey>(`/api/region/journey${q({ from: a, to: b, view })}`),
    stationOutages: (id: string, view: RegionViewName) =>
      call<{ station: { id: string; name: string }; outages: OutageDetail[] }>(`/api/region/stations/${encodeURIComponent(id)}/outages?view=${view}`),
    reconciliation: () => call<Reconciliation>("/api/region/reconciliation?limit=400"),
    reach: (id: string, view: RegionViewName) => call<Reach>(`/api/region/reach${q({ from: id, view })}`),
  },
  queries: () => call<{ store: string; queries: { at: string; cypher: string; param_keys: string[]; rows: number; ms: number }[]; catalog: Record<string, string> }>("/api/debug/queries?limit=40"),
};
