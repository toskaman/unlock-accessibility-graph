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
  relate_crosscheck: { all_match: boolean; stations: { station_name: string; engine: number; cypher: number; match: boolean }[] };
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

export interface LiftCandidate {
  lift_id: string; lift_name: string | null; description: string | null; station_id: string; station_name: string;
  score: number; evidence: string[]; published_state: LiftState; raw_state: string | null;
  pairs_depending?: number; would_lose_if_unavailable?: number;
}
export interface Resolution {
  status: "RESOLVED" | "AMBIGUOUS" | "NOT_FOUND"; text: string; reported_state: LiftState;
  station_candidates: { station_id: string; name: string; score: number }[];
  lift_candidates: LiftCandidate[]; question: string | null; method: string;
}
export interface CriticalLift {
  lift_id: string; lift_name: string | null; description: string | null; station_id: string; station_name: string;
  would_lose: number; pairs_depending: number; covered_by_alternative: number;
}
export interface Critical { evaluated_lifts: number; single_points_of_failure: number; total_confirmed_at_risk: number; lifts: CriticalLift[] }

// ---- region (network mode)
export type RegionViewName = "best" | "feed" | "published";
export type PointState = "OPEN" | "DOUBT" | "CLOSED";
export type ViewSummary = { view: RegionViewName; confirmed: number; possible: number; stations_confirmed: number;
  boarding_points: { total: number; doubt: number; closed: number }; stations_affected: number };
export type FeedInfo = { id: string; observed_at: string; last_lift_update: string | null; last_other_update: string | null;
  lift_messages_stale_days: number | null; licence: string; source: string };
export type RegionCompareRow = { code: string; name: string; network: string; stations: number; accessible_stations: number;
  published: number; confirmed: number; possible: number; share_confirmed: number | null; stations_affected: number;
  sncf_lifts: number; sncf_lifts_out: number; sncf_lifts_unknown: number; ratp_lifts_out: number | null;
  accessible_stations_with_lifts: number; with_platform_exit_topology: number; sncf_status_observed_at: string | null; method: string };
export type RegionInfo = { code: string; name: string; network_label: string; center: [number, number]; zoom: number; default?: boolean };
export type RegionOverview = {
  available: boolean; feed: FeedInfo | null; region: RegionInfo; has_feed: boolean;
  idfm_status: { observed_at: string; observed_paris?: string; night_closure_suspected?: number; ratp_lifts: number; ratp_unavailable: number; ratp_unknown: number; points_closed: number; points_doubt: number } | null;
  entries_source: { key: string; title: string; role: string; licence: string } | null;
  network: { stations: number; stations_with_boardable_platform: number; boardable_platforms: number; boarding_points: number; lines: number; stations_with_station_topology: number };
  views: Record<RegionViewName, ViewSummary>;
  outages: { lifts: number; by_operator: Record<string, number>; messages: number; older_than_30_days: number; older_than_90_days: number; oldest_days: number | null; announced_end_passed: number };
  reconciliation: Record<string, number>;
  feed_watch: { observations: number; first_observed: string; last_observed: string; identical_lift_content: number; identical_since: string; all_identical: boolean;
    history: { observed_at: string; lifts: number; messages: number; feed_last_lift_update: string; feed_non_lift_last_update: string; lift_content_sha: string }[] } | null;
  stale_messages: { messages_contradicted: number; feed_confirmed: number; feed_confirmed_without_them: number; journeys_hidden: number };
  computed_ms: number; method: string;
};
export type RegionStation = { id: string; name: string; lat: number; lon: number; state: PointState | "NOT_BOARDABLE"; outages: number; detail: boolean; sncf_station: string | null; entries_per_day: number | null };
export type ReachClass = "CONFIRMED" | "IF_LIFTS_WORK" | "CUT" | "UNREACHABLE" | "NOT_BOARDABLE";
export type Reach = { origin: { id: string; name: string; lat: number; lon: number }; view: RegionViewName; classes: Record<string, ReachClass>;
  counts: { confirmed: number; if_lifts_work: number; cut: number; published: number };
  entries_per_day: { confirmed: number; if_lifts_work: number; cut: number }; origin_boardable: boolean;
  verification: { engine: number; cypher: number; ok: boolean; rounds: number; ms: number; query: string } };
export type Leg = { board: string; alight: string; line: string; from: string; to: string; line_name: string; mode: string; color: string; text_color: string;
  from_name: string; to_name: string; board_name: string; alight_name: string; board_state: PointState; alight_state: PointState; path: [number, number][] };
export type OutageLabel = { outage?: string; lift?: string; station: string; station_id?: string; text?: string; operator: string; first_reported?: string | null; lines?: string[]; name?: string; state?: string };
export type Journey = { from: { id: string; name: string; lat: number; lon: number }; to: { id: string; name: string; lat: number; lon: number }; view: RegionViewName;
  verdict: "STEP_FREE" | "STEP_FREE_IF_LIFTS_WORK" | "CUT_BY_OUTAGES" | "NO_STEP_FREE_ROUTE_PUBLISHED"; legs: Leg[]; reason?: string;
  blocking_outages?: OutageLabel[]; verification: { legs: number; verified: number; ok: boolean } };
export type Repair = OutageLabel & { kind: "RATP_FEED_OUTAGE" | "SNCF_LIFT" | "RATP_LIFT" | "RATP_LIFT_CHECK"; status_note?: string | null; gain: number; entries_per_day?: number | null; region_station_id?: string | null; updated?: string | null; state?: string };
export type Correction = OutageLabel & { verdict: string; gain: number };
export type RegionRank = { base_live_confirmed: number; base_feed_confirmed: number; repairs: Repair[]; corrections: Correction[]; computed_ms: number; method: string };
export type OutageDetail = { id: string; lift_key: string; operator: string; text: string; station: { id: string; name: string }; first_reported: string | null; days_reported: number | null;
  last_update: string | null; announced_until: string | null; messages: number; lines: string[]; platforms: { id: string; derivation: string; line: string }[];
  matched_lifts: { id: string; name: string | null; sncf_state: string; evidence: string[] }[]; sncf_station_all_working: boolean | null };
export type Reconciliation = { counts: Record<string, number>; feed: FeedInfo;
  rows: { outage: string; lift: string | null; verdict: string; sncf_state?: string; station: string; text: string; lift_name: string | null; evidence?: string[] }[];
  missing_from_feed: { lift: string; name: string; station: string }[] };
export type AgentSession = { id: string; who: string; prompt: string; model?: string | null; seconds?: number | null;
  calls: { name: string; input: Record<string, unknown>; result: string; truncated: boolean }[]; answer: string };
export type FieldReport = { id: string; lift: string; status: "OUT" | "WORKING"; note: string; source: string; reporter: string;
  reported_at: string; station_id: string | null; station: string | null; operator: string | null; label: string;
  official_status: string; official_source: string | null; official_updated: string | null;
  verdict: "CONFIRMS" | "CONTRADICTS" | "NEW_INFO"; age_hours: number; recent: boolean;
  other_official?: { source: string; status: string; updated: string | null; agrees: boolean } };
export type FieldReportIn = { lift: string; status: "OUT" | "WORKING"; note?: string; source?: "rider" | "staff" | "agent"; reporter?: string };
export type TripStatusName = "OK" | "DETOUR" | "AT_RISK" | "CUT" | "NO_STEP_FREE_ROUTE" | "UNKNOWN_STATION";
export type SavedTrip = { label?: string | null; from: { id: string; name: string }; to: { id: string; name: string };
  usual?: { board: string; alight: string; line: string }[]; last_status?: string | null };
export type TripStatus = { status: TripStatusName; message: string; changed?: boolean; previous_status?: string | null;
  from: { id?: string; name: string }; to: { id?: string; name: string }; label?: string;
  observed?: { sncf_lift_status: string | null; idfm_lift_status: string | null };
  usual?: { board: string; alight: string; line: string; board_name: string; alight_name: string; line_name: string }[];
  blocking?: OutageLabel[];
  usual_blocked_at?: { station: string; state: string }[];
  alternative?: { board_name: string; alight_name: string; line_name?: string | null }[] };
