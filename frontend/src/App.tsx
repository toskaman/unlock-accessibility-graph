import { useCallback, useEffect, useMemo, useState } from "react";
import { api, ApiError, setApiRegion, STATIC_DEMO } from "./api";
import { StaticBanner } from "./components/StaticBanner";
import { LangSwitch } from "./components/LangSwitch";
import { LiftGlyph } from "./components/Marks";
import { getLang, tr, useLang } from "./i18n";
import { MapView } from "./components/MapView";
import { RegionView } from "./components/RegionView";
import { STATE_LABEL, StationSection } from "./components/StationSection";
import type { RegionInfo, Analysis, Candidate, Critical, Explanation, LiftCandidate, PairClass, PairView, Ranking, Resolution, StationGraph, StationRow, Summary, View } from "./types";

const CLASS_LABEL: Record<PairClass, string> = {
  CONFIRMED_ACCESSIBLE: "Confirmed step-free",
  CONFIRMED_BLOCKED: "Blocked",
  UNVERIFIED: "Unverified",
  OUT_OF_SCOPE: "No modeled route",
};
const EXAMPLES = [
  "Juvisy : ascenseur quai 50/51 HS depuis ce matin",
  "Lift to platforms G and H at Noisy-le-Sec is out of service",
  "Ascenseur en panne à Pontoise",
];
const CLASS_ORDER: PairClass[] = ["CONFIRMED_ACCESSIBLE", "CONFIRMED_BLOCKED", "UNVERIFIED", "OUT_OF_SCOPE"];
const KIND_LABEL: Record<string, string> = {
  OBSERVATION: "Source record", CALCULATION: "Calculated", SIMULATION: "Simulated", DERIVATION: "Derived from text", UNKNOWN: "Unknown",
};

function fmtAge(h: number | null) {
  if (h == null) return "unknown age";
  if (h < 1) return `${Math.round(h * 60)} min old`;
  if (h < 48) return `${h.toFixed(1)} h old`;
  return `${Math.round(h / 24)} days old`;
}

function downloadJSON(name: string, data: unknown) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
  const a = document.createElement("a");
  a.href = url; a.download = name; a.click();
  URL.revokeObjectURL(url);
}

export default function App() {
  useLang(); // re-render everything when the language changes
  const [mode, setMode] = useState<"region" | "station">(() => (!STATIC_DEMO && location.hash.includes("station=") ? "station" : "region"));
  const [summary, setSummary] = useState<Summary | null>(null);
  const [region, setRegion] = useState<string>("idf");
  const [regions, setRegions] = useState<RegionInfo[]>([]);
  useEffect(() => {
    api.regions().then((rs) => { setRegions(rs); const d = rs.find((r) => r.default); if (d) setRegion(d.code); }).catch(() => setRegions([]));
  }, []);
  const [stations, setStations] = useState<StationRow[]>([]);
  const [stationId, setStationId] = useState<string | null>(null);
  const [graph, setGraph] = useState<StationGraph | null>(null);
  const [lift, setLift] = useState<string | null>(null);
  const [view, setView] = useState<View>("baseline");
  const [scenario, setScenario] = useState<{ id: string; name: string } | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [ranking, setRanking] = useState<Ranking | null>(null);
  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [analyst, setAnalyst] = useState<{ statements: { kind: string; text: string }[]; fluent?: string } | null>(null);
  const [pair, setPair] = useState<PairView | null>(null);
  const [explanation, setExplanation] = useState<Explanation | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [inspect, setInspect] = useState(false);
  const [report, setReport] = useState("");
  const [resolution, setResolution] = useState<Resolution | null>(null);
  const [critical, setCritical] = useState<Critical | null>(null);
  const [rightTab, setRightTab] = useState<"repairs" | "critical">("repairs");
  const [repairCounts, setRepairCounts] = useState<import("./types").Counts | null>(null);
  const [liftDeps, setLiftDeps] = useState<{ pairs_depending: number; confirmed_now: number; would_lose_if_unavailable: number } | null>(null);

  const fail = (e: unknown) => setError(e instanceof ApiError ? e.message : String(e));

  // initial load
  useEffect(() => {
    if (STATIC_DEMO) return;
    setBusy("Loading the network graph…");
    Promise.all([api.summary(), api.stations(), api.rank(null), api.critical()])
      .then(([s, st, r, c]) => {
        setSummary(s); setStations(st); setRanking(r); setCritical(c);
        const fromHash = new URLSearchParams(location.hash.slice(1)).get("station");
        const best = [...st].sort((a, b) => b.confirmed - a.confirmed || a.name.localeCompare(b.name))[0];
        setStationId(st.find((x) => x.id === fromHash || x.name === fromHash)?.id || best?.id || null);
      })
      .catch(fail)
      .finally(() => setBusy(null));
  }, []);

  // station graph for the current view
  useEffect(() => {
    if (!stationId) return;
    const sc = view === "baseline" ? null : scenario?.id;
    const cand = view === "restoration" ? candidate?.lift_id : null;
    api.station(stationId, sc, cand).then(setGraph).catch(fail);
  }, [stationId, view, scenario?.id, candidate?.lift_id]);

  useEffect(() => {
    setLiftDeps(null);
    if (!lift) return;
    api.lift(lift, view === "baseline" ? null : scenario?.id).then(setLiftDeps).catch(() => setLiftDeps(null));
  }, [lift, view, scenario?.id]);

  useEffect(() => {
    if (mode === "region") { history.replaceState(null, "", "#region"); return; }
    if (!stationId) return;
    history.replaceState(null, "", `#station=${encodeURIComponent(stationId)}`);
  }, [stationId, mode]);

  const selectStation = useCallback((id: string) => {
    setStationId(id); setLift(null); setPair(null); setExplanation(null);
  }, []);

  const simulate = async (target?: string) => {
    const id = target || lift;
    if (!id) return;
    setBusy("Simulating the outage and recomputing every modeled route…");
    setError(null);
    try {
      if (scenario) await api.deleteScenario(scenario.id).catch(() => undefined);
      const r = await api.simulate([id]);
      setScenario(r.scenario); setAnalysis(r.analysis); setCandidate(null); setAnalyst(null);
      setView("outage");
      setRanking(await api.rank(r.scenario.id));
      setPair(null); setExplanation(null);
    } catch (e) { fail(e); } finally { setBusy(null); }
  };

  const restoreBaseline = async () => {
    if (scenario) await api.deleteScenario(scenario.id).catch(() => undefined);
    setScenario(null); setAnalysis(null); setCandidate(null); setAnalyst(null); setView("baseline");
    setPair(null); setExplanation(null);
    api.rank(null).then(setRanking).catch(fail);
  };

  const chooseCandidate = async (c: Candidate) => {
    setRightTab("repairs");
    setCandidate(c); setView(scenario ? "restoration" : "baseline");
    if (c.station_id !== stationId) setStationId(c.station_id);
    setLift(c.lift_id); setPair(null); setExplanation(null);
    setRepairCounts(null);
    if (scenario) {
      api.explainCandidate(scenario.id, c.lift_id).then(setAnalyst).catch(fail);
      api.withCandidate(scenario.id, c.lift_id).then((r) => setRepairCounts(r.with_candidate_counts)).catch(fail);
    }
  };

  const findLift = async (text?: string) => {
    const t = (text ?? report).trim();
    if (t.length < 3) return;
    if (text) setReport(text);
    setError(null);
    try { setResolution(await api.resolve(t)); } catch (e) { fail(e); }
  };

  const pickCandidate = (c: LiftCandidate, andSimulate: boolean) => {
    setStationId(c.station_id); setLift(c.lift_id); setPair(null); setExplanation(null);
    if (andSimulate) simulate(c.lift_id);
  };

  const openPair = async (p: PairView) => {
    setPair(p);
    try {
      const sc = view === "baseline" ? null : scenario?.id;
      const cand = view === "restoration" ? candidate?.lift_id : (view === "outage" ? lift : null);
      setExplanation(await api.explain(p.id, sc, cand));
    } catch (e) { fail(e); }
  };

  const exportReport = async () => {
    if (!scenario) return;
    try { downloadJSON(`unlock-${scenario.id}.json`, await api.export(scenario.id)); } catch (e) { fail(e); }
  };

  const simulated = useMemo(() => new Set(Object.keys(analysis?.overrides || {})), [analysis]);
  // spaces cut off: every connection that was confirmed step-free at baseline is lost in this view
  const lostSpaces = useMemo(() => {
    const had = new Map<string, number>(), lost = new Map<string, number>();
    graph?.pairs.forEach((p) => {
      if (p.baseline_cls !== "CONFIRMED_ACCESSIBLE") return;
      [p.a, p.b].forEach((x) => {
        had.set(x, (had.get(x) || 0) + 1);
        if (p.cls !== "CONFIRMED_ACCESSIBLE") lost.set(x, (lost.get(x) || 0) + 1);
      });
    });
    return new Set([...had].filter(([x, n]) => (lost.get(x) || 0) === n).map(([x]) => x));
  }, [graph]);
  const liftInfo = graph?.lifts.find((l) => l.id === lift) || null;
  const highlight = pair ? (explanation?.pair.id === pair.id ? explanation.routes.flatMap((r) => r.path?.nodes.map((n: any) => n.id) || []) : pair.routes.flatMap((r) => r.nodes)) : null;
  const station = stations.find((s) => s.id === stationId);
  const matches = search.length > 1 ? stations.filter((s) => s.name.toLowerCase().includes(search.toLowerCase())).slice(0, 8) : [];

  const netBase = analysis?.baseline_counts || summary?.pairs;
  const netNow = view === "baseline" ? summary?.pairs : view === "restoration" ? repairCounts || analysis?.scenario_counts : analysis?.scenario_counts;

  const sortedPairs = useMemo(() => {
    if (!graph) return [];
    const changed = (p: PairView) => (p.cls !== p.baseline_cls ? 0 : 1);
    return [...graph.pairs].sort((a, b) => changed(a) - changed(b) || CLASS_ORDER.indexOf(a.cls) - CLASS_ORDER.indexOf(b.cls) || a.a_name.localeCompare(b.a_name));
  }, [graph]);

  const modeTabs = (
    <nav className="modes" aria-label={tr("Scale", "Échelle")}>
      <button aria-current={mode === "region" ? "page" : undefined} className={mode === "region" ? "on" : ""} onClick={() => setMode("region")}>{tr("Whole region", "Toute la région")}</button>
      <button aria-current={mode === "station" ? "page" : undefined} className={mode === "station" ? "on" : ""} onClick={() => setMode("station")}>{tr("Inside a station", "Dans une gare")}</button>
    </nav>
  );

  if (mode === "region") {
    return (
      <div className="app region-mode">
        <header className="top">
          <div className="brand">
            <h1><LiftGlyph size={24} />UNLOCK</h1>
            <p>{tr("Find the repair that unlocks the most journeys.", "Trouver la réparation qui rend le plus de trajets.")}</p>
          </div>
          {!STATIC_DEMO && modeTabs}
          {!STATIC_DEMO && <div className="meta"><button className="ghost" onClick={() => setInspect(true)}>{tr("Inspect the graph", "Explorer le graphe")}</button></div>}
          <LangSwitch />
        </header>
        {STATIC_DEMO && <StaticBanner region={region} />}
        {error && <div className="banner error" role="alert">{error} <button className="ghost" onClick={() => setError(null)}>{tr("Dismiss", "Fermer")}</button></div>}
        <RegionView key={region} region={region} regions={regions} onRegion={(c) => { setApiRegion(regions.find((r) => r.code === c)?.default ? null : c); setRegion(c); }}
          onError={setError} onOpenStation={(id) => { setApiRegion(null); setRegion("idf"); setMode("station"); selectStation(id); }} />
        {inspect && <Inspector summary={summary} onClose={() => setInspect(false)} />}
      </div>
    );
  }

  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <h1><LiftGlyph size={24} />UNLOCK</h1>
          <p>Find the repair that unlocks the most journeys.</p>
        </div>
        {modeTabs}
        <div className="viewswitch" role="tablist" aria-label="Compare states">
          {(["baseline", "outage", "restoration"] as View[]).map((v) => (
            <button key={v} role="tab" aria-selected={view === v} className={view === v ? "on" : ""}
                    disabled={(v === "outage" && !scenario) || (v === "restoration" && !(scenario && candidate))}
                    onClick={() => setView(v)}>
              {v === "baseline" ? "Published status" : v === "outage" ? "Simulated outage" : "With proposed repair"}
            </button>
          ))}
        </div>
        <div className="meta">
          {summary && (
            <span className={`fresh f-${summary.status.freshness}`} title={`Snapshot ${summary.status.snapshot_id}, observed ${summary.status.observed_at}`}>
              Lift status: {summary.status.freshness.toLowerCase()} · {fmtAge(summary.status.age_hours)}
            </span>
          )}
          <button className="ghost" onClick={() => setInspect(true)}>Inspect the graph</button>
        </div>
        <LangSwitch />
      </header>
      {getLang() === "fr" && <div className="banner static-banner" role="note" lang="fr">La vue « dans une gare » n'existe pour l'instant qu'en anglais. La vue <em>Toute la région</em> est entièrement en français.</div>}

      {error && <div className="banner error" role="alert">{error} <button className="ghost" onClick={() => setError(null)}>{tr("Dismiss", "Fermer")}</button></div>}
      {view !== "baseline" && <div className="banner sim" role="status">Simulated scenario — {scenario?.name}. Published lift observations are unchanged.</div>}

      <aside className="left">
        <section className="report" aria-labelledby="report-h">
          <h2 id="report-h">Start from an outage report</h2>
          <textarea value={report} onChange={(e) => setReport(e.target.value)} rows={3}
                    placeholder="Paste what the operator or a traveller wrote, e.g. “Juvisy : ascenseur quai 50/51 HS”"
                    onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) findLift(); }} />
          <div className="report-actions">
            <button className="primary small" onClick={() => findLift()} disabled={report.trim().length < 3}>Find the lift</button>
            <span className="muted small">or try:</span>
          </div>
          <div className="chips">
            {EXAMPLES.map((x) => <button key={x} className="chip" onClick={() => findLift(x)}>{x}</button>)}
          </div>
          {resolution && (
            <div className={`resolution r-${resolution.status}`} aria-live="polite">
              {resolution.status === "RESOLVED" && (() => {
                const c = resolution.lift_candidates[0];
                return (
                  <>
                    <p className="rtitle">Found in the graph: <strong>{c.lift_name}</strong> at {c.station_name}</p>
                    <ul className="ev">{c.evidence.map((e, i) => <li key={i}>{e}</li>)}</ul>
                    <p className="small">Published status: {c.raw_state ?? "none"} · {c.pairs_depending ?? 0} modeled connections can use it
                      {c.would_lose_if_unavailable ? <>; <strong>{c.would_lose_if_unavailable}</strong> would be lost</> : null}.</p>
                    <div className="report-actions">
                      <button className="primary small" onClick={() => pickCandidate(c, resolution.reported_state === "UNAVAILABLE")}>
                        {resolution.reported_state === "UNAVAILABLE" ? "Simulate this outage" : "Show this lift"}
                      </button>
                    </div>
                  </>
                );
              })()}
              {resolution.status === "AMBIGUOUS" && (
                <>
                  <p className="rtitle">{resolution.question} UNLOCK won't guess — pick one:</p>
                  <ul className="cands">
                    {resolution.lift_candidates.map((c) => (
                      <li key={c.lift_id}><button onClick={() => pickCandidate(c, false)}>
                        <strong>{c.lift_name}</strong> <span className="muted">{c.station_name} · {c.description}</span>
                      </button></li>
                    ))}
                  </ul>
                </>
              )}
              {resolution.status === "NOT_FOUND" && <p className="rtitle">{resolution.question}</p>}
              <p className="muted tiny">Matched deterministically against the Relate graph (station and zone names, the platforms and spaces each lift serves). No AI guessing.</p>
            </div>
          )}
        </section>
        <label className="search">
          <span>Find a station</span>
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="e.g. Juvisy, Gare du Nord" aria-describedby="search-help" />
        </label>
        <span id="search-help" className="sr-only">Type at least two letters, then choose a station from the list.</span>
        {matches.length > 0 && (
          <ul className="matches" role="listbox" aria-label="Matching stations">
            {matches.map((s) => (
              <li key={s.id}><button role="option" aria-selected={s.id === stationId} onClick={() => { selectStation(s.id); setSearch(""); }}>
                {s.name} <small>{s.lifts} lifts</small></button></li>
            ))}
          </ul>
        )}
        <MapView stations={stations} selected={stationId} affected={view === "baseline" ? {} : analysis?.lost_by_station || {}} onSelect={selectStation} />
        <div className="legend" aria-label="Map legend">
          <span><i className="dot ink" />Station with lifts</span>
          <span><i className="dot amber" />A lift out of service now</span>
          <span><i className="dot red" />Loses connections in the scenario</span>
        </div>
        {summary && (
          <dl className="netfacts">
            <div><dt>Stations</dt><dd>{summary.stations}</dd></div>
            <div><dt>Lifts</dt><dd>{summary.lifts}</dd></div>
            <div><dt>Out of service now</dt><dd>{summary.lift_states.UNAVAILABLE || 0}</dd></div>
            <div><dt>Status unknown</dt><dd>{summary.lift_states.UNKNOWN || 0}</dd></div>
          </dl>
        )}
      </aside>

      <main className="center">
        {graph && station ? (
          <>
            <div className="station-head">
              <div>
                <h2>{graph.station.name}</h2>
                <p className="lines">
                  {graph.station.lines.length ? graph.station.lines.map((l) => (
                    <span key={l.id} className="line" style={{ background: l.color ? `#${l.color}` : undefined, color: l.text_color ? `#${l.text_color}` : undefined }}
                          title={`${l.mode.toLowerCase()} ${l.short_name}`}>{l.short_name}</span>
                  )) : <span className="muted">No rail, metro or tram line matched</span>}
                  {graph.station.zone.name && <span className="muted"> IDFM transfer zone {graph.station.zone.name}</span>}
                </p>
              </div>
              <StationCounts graph={graph} />
            </div>

            <StationSection graph={graph} selectedLift={lift} simulated={simulated} candidate={view === "restoration" ? candidate?.lift_id || null : null}
                            highlight={highlight} lostSpaces={lostSpaces} onSelectLift={(id) => { setLift(id); setPair(null); setExplanation(null); }} />
            <div className="section-legend" aria-hidden="true">
              <span><i className="cab ok" />Working</span><span><i className="cab ko" />Out of service</span>
              <span><i className="cab unk" />Status unknown</span><span><i className="ring rs" />Simulated outage</span>
              <span><i className="ring rc" />Proposed repair</span><span><i className="bar hatch" />Source says not step-free</span>
            </div>

            <section className="liftbar" aria-live="polite">
              {liftInfo ? (
                <>
                  <div>
                    <h3>{liftInfo.name || liftInfo.id}</h3>
                    <p>{liftInfo.description || "The source gives no location text for this lift."}</p>
                    <p className="muted">Published status: <strong>{liftInfo.raw_state ?? "none"}</strong> ({STATE_LABEL[liftInfo.baseline].toLowerCase()})
                      {liftInfo.overridden && " · overridden in this simulation"}</p>
                    {view === "restoration" && candidate?.lift_id === liftInfo.id && (
                      <p className="deps repair">Proposed repair in this view: restoring it brings back <strong>{candidate.gain}</strong> confirmed step-free connection{candidate.gain === 1 ? "" : "s"} network-wide.</p>
                    )}
                    {view !== "restoration" && liftDeps && liftInfo.state === "UNAVAILABLE" && (
                      <p className="deps">Out of service in this view. {liftDeps.pairs_depending} modeled connection{liftDeps.pairs_depending === 1 ? "" : "s"} can use it — the ranking shows what repairing it restores.</p>
                    )}
                    {view !== "restoration" && liftDeps && liftInfo.state !== "UNAVAILABLE" && (
                      <p className="deps">
                        {liftDeps.pairs_depending === 0
                          ? "No modeled connection runs through this lift, so an outage would change nothing here."
                          : <>{liftDeps.pairs_depending} modeled connection{liftDeps.pairs_depending === 1 ? "" : "s"} can use this lift. If it stops, <strong>{liftDeps.would_lose_if_unavailable}</strong> confirmed step-free connection{liftDeps.would_lose_if_unavailable === 1 ? "" : "s"} would be lost{liftDeps.would_lose_if_unavailable < liftDeps.confirmed_now ? "; the rest have another working route" : ""}.</>}
                      </p>
                    )}
                  </div>
                  <div className="actions">
                    <button className="primary" onClick={() => simulate()} disabled={!!busy || liftInfo.state === "UNAVAILABLE" || view === "restoration"}
                            title={view === "restoration" ? "Switch to the published status or the outage view to simulate another outage" : liftInfo.state === "UNAVAILABLE" ? "This lift is already out of service in this view" : undefined}>
                      Simulate outage
                    </button>
                    {scenario && <button onClick={restoreBaseline}>Restore published status</button>}
                    {scenario && <button onClick={exportReport}>Export report</button>}
                  </div>
                </>
              ) : (
                <p className="hint">Select a lift in the cross-section to see what depends on it, then simulate its outage.</p>
              )}
            </section>

            <section className="pairs">
              <h3>Connections in this station <span className="muted">platform ↔ platform and platform ↔ exit, modeled from lift data</span></h3>
              {sortedPairs.length === 0 ? <p className="empty">No platform or exit spaces could be identified for this station.</p> : (
                <ul>
                  {sortedPairs.map((p) => (
                    <li key={p.id}>
                      <button className={`pair c-${p.cls}${p.cls !== p.baseline_cls ? " changed" : ""}${pair?.id === p.id ? " active" : ""}`} onClick={() => openPair(p)}>
                        <span className="ends">{p.a_name} <span aria-hidden="true">↔</span><span className="sr-only">to</span> {p.b_name}</span>
                        <span className="cls">
                          {p.cls !== p.baseline_cls && <s>{CLASS_LABEL[p.baseline_cls]}</s>} {CLASS_LABEL[p.cls]}
                        </span>
                        <span className="routes">{p.routes.length} route{p.routes.length === 1 ? "" : "s"}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </>
        ) : <p className="empty">{busy || "Choose a station on the map."}</p>}
      </main>

      <aside className="right">
        <section className="impact" aria-live="polite">
          <h3>{view === "baseline" ? "Network today" : view === "outage" ? "Impact of the simulated outage" : "Impact with the proposed repair"}</h3>
          {netBase && netNow && (
            <ul className="counts">
              {CLASS_ORDER.map((c) => {
                const now = netNow[c];
                const d = now - netBase[c];
                return (
                  <li key={c} className={`c-${c}`}>
                    <span className="n">{now}</span>
                    <span className="lbl">{CLASS_LABEL[c]}</span>
                    {view !== "baseline" && d !== 0 && <span className={`d ${d > 0 ? "up" : "down"}`}>{d > 0 ? "+" : ""}{d}</span>}
                  </li>
                );
              })}
            </ul>
          )}
          {view !== "baseline" && analysis?.relate_crosscheck && (
            <p className={`xcheck ${analysis.relate_crosscheck.all_match ? "ok" : "bad"}`}>
              Cross-checked in Cypher: {analysis.relate_crosscheck.stations.map((c) => `${c.station_name} ${c.engine} = ${c.cypher}`).join(" · ")}
              {analysis.relate_crosscheck.all_match ? " — engine and Relate query agree." : " — MISMATCH, see /api/debug/queries."}
            </p>
          )}
          {summary && (
            <p className="muted small">
              {summary.pairs.TOTAL} modeled station connections across Île-de-France; {summary.coverage.numerator} ({Math.round((summary.coverage.ratio || 0) * 100)}%) have at least one lift route in the source data.
              Counts are connections, not people.
            </p>
          )}
        </section>

        {candidate && (
          <section className="analyst">
            <h3>Why this repair</h3>
            <p>{candidate.reason}.</p>
            {candidate.still_blocked_by_others.length > 0 && <p className="warn">Another unavailable lift blocks the same connections — repair them together.</p>}
            {analyst?.fluent && <p className="fluent">{analyst.fluent}</p>}
            {analyst && <ul className="stmts">{analyst.statements.map((s, i) => <li key={i}><em className={`k k-${s.kind}`}>{KIND_LABEL[s.kind] || s.kind}</em> {s.text}</li>)}</ul>}
          </section>
        )}

        {explanation && pair && (
          <section className="evidence">
            <div className="evhead">
              <h3>Evidence: {pair.a_name} ↔ {pair.b_name}</h3>
              <button className="ghost small" onClick={() => { setPair(null); setExplanation(null); }}>Close</button>
            </div>
            <ul className="stmts">
              {explanation.narrative.statements.map((s, i) => <li key={i}><em className={`k k-${s.kind}`}>{KIND_LABEL[s.kind] || s.kind}</em> {s.text}</li>)}
            </ul>
            {explanation.routes.map((r, i) => (
              <div key={i} className="route">
                <p className="small"><strong>Route {i + 1}</strong> — {r.state.toLowerCase()} {r.restored_state && r.restored_state !== r.state && <>→ {r.restored_state.toLowerCase()} with the repair</>}</p>
                <p className="chain">
                  {(r.path?.nodes || []).map((n: any, j: number) => (
                    <span key={j} className={`node ${n.labels?.[0] === "Lift" ? "lift" : "space"}`}>{n.labels?.[0] === "Lift" ? (n.name || "Lift") : n.name}</span>
                  ))}
                </p>
                <p className="muted small">Relationships: {(r.path?.relationships || []).map((x: any) => `${x.type} (${x.derivation})`).join(", ")}</p>
              </div>
            ))}
            <p className="muted small">Sources: {[...new Set(explanation.routes.flatMap((r) => r.lifts.flatMap((l) => [l.evidence?.status_dataset?.title, l.evidence?.description_dataset?.title])).filter(Boolean))].join("; ")}</p>
          </section>
        )}
        <div className="rtabs" role="tablist" aria-label="Ranking lists">
          <button role="tab" aria-selected={rightTab === "repairs"} className={rightTab === "repairs" ? "on" : ""} onClick={() => setRightTab("repairs")}>Repairs to make</button>
          <button role="tab" aria-selected={rightTab === "critical"} className={rightTab === "critical" ? "on" : ""} onClick={() => setRightTab("critical")}>Lifts you can't lose</button>
        </div>
        {rightTab === "critical" && critical && (
          <section className="critical">
            <p className="small">{critical.single_points_of_failure} of {critical.evaluated_lifts} working lifts on modeled routes are a single point of failure: if one stops, confirmed step-free connections are lost with no modeled alternative.</p>
            <ol>
              {critical.lifts.slice(0, 12).map((c) => (
                <li key={c.lift_id}>
                  <button className={`cand${lift === c.lift_id ? " active" : ""}`} onClick={() => { setStationId(c.station_id); setLift(c.lift_id); setPair(null); setExplanation(null); }}>
                    <span className="gain"><strong className="risk">−{c.would_lose}</strong><span className="bar risk" style={{ width: `${(c.would_lose / Math.max(1, critical.lifts[0].would_lose)) * 100}%` }} /></span>
                    <span className="who">{c.station_name}<small>{c.lift_name}</small></span>
                    <span className="tag ko">{c.covered_by_alternative ? `${c.covered_by_alternative} covered by another route` : "no alternative route"}</span>
                  </button>
                </li>
              ))}
            </ol>
            <p className="muted small">Each lift evaluated alone against today's published status. Select one, then simulate its outage.</p>
          </section>
        )}
        {rightTab === "repairs" && <section className="ranking">
          <h3>{scenario ? "Repairs ranked by connections restored" : "Repairs ranked on today's published status"}</h3>
          {!ranking ? <p className="muted">Ranking…</p> : ranking.candidates.length === 0 ? (
            <p className="empty">No lift is out of service or unknown on a modeled route — there is nothing to repair.</p>
          ) : (
            <ol>
              {ranking.candidates.slice(0, 12).map((c) => {
                const max = Math.max(1, ranking.candidates[0].gain);
                return (
                  <li key={c.lift_id}>
                    <button className={`cand${candidate?.lift_id === c.lift_id ? " active" : ""}`} onClick={() => chooseCandidate(c)}>
                      <span className="gain"><strong>+{c.gain}</strong><span className="bar" style={{ width: `${(c.gain / max) * 100}%` }} /></span>
                      <span className="who">{c.station_name}<small>{c.lift_name}</small></span>
                      <span className={`tag ${c.simulated ? "sim" : c.current_state === "UNKNOWN" ? "unk" : "ko"}`}>
                        {c.simulated ? "Simulated" : c.current_state === "UNKNOWN" ? "Unknown status" : "Out of service now"}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ol>
          )}
          {ranking && <p className="muted small">Gain = change in confirmed step-free connections if only that lift is repaired. {ranking.candidate_count} candidates evaluated.</p>}
        </section>}
      </aside>

      {busy && <div className="busy" role="status">{busy}</div>}
      {inspect && <Inspector summary={summary} onClose={() => setInspect(false)} />}
    </div>
  );
}

function StationCounts({ graph }: { graph: StationGraph }) {
  return (
    <ul className="station-counts" aria-label="Connections in this station">
      {CLASS_ORDER.map((c) => {
        const d = graph.counts[c] - graph.baseline_counts[c];
        return (
          <li key={c} className={`c-${c}`}>
            <strong>{graph.counts[c]}</strong> {CLASS_LABEL[c].toLowerCase()}
            {d !== 0 && <span className={`d ${d > 0 ? "up" : "down"}`}> ({d > 0 ? "+" : ""}{d})</span>}
          </li>
        );
      })}
    </ul>
  );
}

function Inspector({ summary, onClose }: { summary: Summary | null; onClose: () => void }) {
  const [data, setData] = useState<Awaited<ReturnType<typeof api.queries>> | null>(null);
  useEffect(() => { api.queries().then(setData).catch(() => undefined); }, []);
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [onClose]);
  return (
    <div className="modal" role="dialog" aria-modal="true" aria-label="Inspect the Relate graph">
      <div className="sheet">
        <header><h2>Inside the Relate store</h2><button onClick={onClose} autoFocus>Close</button></header>
        {summary && (
          <>
            <p className="small">Persistent single-file store <code>{summary.store}</code> · algorithm {summary.algorithm_version}</p>
            <div className="cols">
              <table><caption>Nodes</caption><tbody>{Object.entries(summary.graph.nodes).map(([k, v]) => <tr key={k}><th>{k}</th><td>{v}</td></tr>)}</tbody></table>
              <table><caption>Relationships</caption><tbody>{Object.entries(summary.graph.relationships).map(([k, v]) => <tr key={k}><th>{k}</th><td>{v}</td></tr>)}</tbody></table>
            </div>
            <h3>Sources</h3>
            <ul className="small">{summary.datasets.map((d) => <li key={d.key}><strong>{d.title}</strong> — {d.publisher}, {d.licence}. Retrieved {d.retrieved_at}, sha256 {d.sha256.slice(0, 12)}…</li>)}</ul>
          </>
        )}
        <h3>Route traversal (Cypher)</h3>
        <pre>{data?.catalog.routes}</pre>
        <h3>Recent statements executed by Relate</h3>
        <ol className="qlog">
          {data?.queries.map((q, i) => <li key={i}><span className="ms">{q.ms} ms · {q.rows} rows</span><code>{q.cypher}</code></li>)}
        </ol>
      </div>
    </div>
  );
}
