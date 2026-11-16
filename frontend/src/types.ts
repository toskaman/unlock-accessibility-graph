export type LiftState = "AVAILABLE" | "UNAVAILABLE" | "UNKNOWN";
export type PairClass = "CONFIRMED_ACCESSIBLE" | "CONFIRMED_BLOCKED" | "UNVERIFIED" | "OUT_OF_SCOPE";
export type View = "baseline" | "outage" | "restoration";

export interface Counts {
  CONFIRMED_ACCESSIBLE: number;
  CONFIRMED_BLOCKED: number;
  UNVERIFIED: number;
  OUT_OF_SCOPE: number;
  TOTAL: number;
}

export interface Line { id: string; short_name: string; mode: string; color: string | null; text_color: string | null }

export interface Freshness { snapshot_id: string; observed_at: string | null; freshness: string; age_hours: number | null }

export interface Summary {
  algorithm_version: string;
  store: string;
  graph: { nodes: Record<string, number>; relationships: Record<string, number> };
  datasets: { key: string; title: string; publisher: string; licence: string; sha256: string; retrieved_at: string; publisher_modified: string | null; url: string }[];
  status: Freshness;
  stations: number;
  lifts: number;
  lift_states: Record<string, number>;
  pairs: Counts;
  pairs_with_modeled_route: number;
  coverage: { numerator: number; denominator: number; ratio: number | null };
}

export interface StationRow {
  id: string; name: string; lon: number; lat: number; lines: Line[]; lifts: number;
  lift_states: Record<string, number>; pairs: number; confirmed: number; blocked: number; unverified: number; out_of_scope: number;
}

export interface Space { id: string; name: string; role: string; quay_id: string | null; quay_name: string | null; step_free: string | null }
export interface LiftView { id: string; name: string | null; description: string | null; baseline: LiftState; raw_state: string | null; state: LiftState; overridden: boolean }
export interface Serves { lift: string; space: string; derivation: string; side_text: string }
export interface RouteView { lifts: string[]; nodes: string[]; state: LiftState }
export interface PairView {
  id: string; a: string; b: string; a_name: string; b_name: string; a_role: string; b_role: string; kind: string;
  a_assertion: string; b_assertion: string; routes: RouteView[]; cls: PairClass; reason: string; baseline_cls: PairClass;
  blocking_lifts: string[]; unknown_lifts: string[];
}

export interface StationGraph {
  station: { id: string; name: string; lon: number; lat: number; zone: { id: string | null; name: string | null }; lines: Line[] };
  spaces: Space[]; lifts: LiftView[]; serves: Serves[]; pairs: PairView[];
  counts: Counts; baseline_counts: Counts; scenario_id: string | null; candidate_lift: string | null;
}

export interface Analysis {
  analysis_id: string; scenario_id: string; scenario_name: string; algorithm_version: string; snapshot: Freshness;
  input_hash: string; overrides: Record<string, LiftState>; baseline_counts: Counts; scenario_counts: Counts;
  lost_confirmed: string[]; gained_confirmed: string[]; transitions: Record<string, number>;
  affected_stations: string[]; lost_by_station: Record<string, number>;
}

export interface Candidate {
  rank: number; lift_id: string; lift_name: string | null; description: string | null; station_id: string; station_name: string;
  current_state: LiftState; baseline_state: LiftState; simulated: boolean; gain: number; restored_pairs: string[];
  resolved_unverified: number; pairs_depending: number; still_blocked_by_others: string[]; reason: string;
}

export interface Ranking { scenario_id: string | null; confirmed_now: number; candidates: Candidate[]; candidate_count: number; metric: string }

export interface Statement { kind: string; text: string }
export interface Explanation {
  pair: PairView;
  classification: { scenario: PairClass; reason: string; baseline: PairClass; with_candidate: PairClass | null; candidate_lift: string | null };
  routes: {
    state: LiftState; baseline_state: LiftState; restored_state: LiftState | null;
    lifts: { id: string; name: string | null; state: LiftState; baseline: LiftState; overridden: boolean; evidence: any }[];
    path: { nodes: any[]; relationships: any[] } | null;
  }[];
  endpoints: { a: any; b: any };
  unknowns: string[];
  narrative: { mode: string; statements: Statement[] };
  snapshot: Freshness;
}
