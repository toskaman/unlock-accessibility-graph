import { useEffect, useMemo, useState } from "react";
import { api, ApiError, bulletinUrl, STATIC_DEMO } from "../api";
import type { RegionCompareRow, RegionInfo, Journey, OutageDetail, Reach, Reconciliation, RegionOverview, RegionRank, RegionStation, RegionViewName } from "../types";
import { TripWatch } from "./TripWatch";
import { HistoryChart } from "./HistoryChart";
import { RegionMap } from "./RegionMap";

const VIEW_LABEL: Record<RegionViewName, string> = {
  best: "Best available status",
  feed: "PRIM outage feed",
  published: "Published network",
};
const VIEW_HELP: Record<RegionViewName, string> = {
  best: "SNCF's hourly lift status + IDFM's lift status for RATP (refreshed several times a day), both read on station lift graphs",
  feed: "Every lift outage listed in the PRIM traffic-information feed",
  published: "Platforms declared wheelchair-boardable, no outage at all",
};
const VIEW_PHRASE: Record<RegionViewName, string> = {
  best: "with the best available lift status",
  feed: "according to the PRIM outage feed",
  published: "in the published network, ignoring outages",
};
const VERDICT: Record<Journey["verdict"], { cls: string; title: string }> = {
  STEP_FREE: { cls: "v-ok", title: "Step-free journey" },
  STEP_FREE_IF_LIFTS_WORK: { cls: "v-doubt", title: "Possible only if listed lifts work" },
  CUT_BY_OUTAGES: { cls: "v-cut", title: "Cut by reported outages" },
  NO_STEP_FREE_ROUTE_PUBLISHED: { cls: "v-none", title: "No step-free route in the published network" },
};
const STATE_WORD = { OPEN: "open", DOUBT: "lift listed out", CLOSED: "cut off" } as const;
const EXAMPLES: Record<string, [string, string, string, string][]> = {
  idf: [["73798", "Rosa Parks", "478505", "Juvisy"], ["65582", "Garges - Sarcelles", "71410", "Gare du Nord"]],
  ara: [["OCE87721175", "Lyon Gorge de Loup", "OCE87723197", "Lyon Part Dieu"], ["OCE87747006", "Grenoble", "OCE87722587", "Vienne"]],
};
const n = (x: number | undefined | null) => (x == null ? "—" : x.toLocaleString("en-GB"));
const date = (s?: string | null) => (s ? new Date(s.length <= 19 ? s + "Z" : s).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : "—");
const stamp = (s?: string | null) => (s ? new Date(s).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "UTC" }) + " UTC" : "—");
const days = (s?: string | null) => (s ? Math.floor((Date.now() - new Date(s.length <= 19 ? s + "Z" : s).getTime()) / 86400000) : null);

function LineBadge({ name, color, text }: { name?: string | null; color?: string | null; text?: string | null }) {
  return <span className="line" style={{ background: color ? `#${color}` : undefined, color: text ? `#${text}` : undefined }}>{name}</span>;
}

function StationPicker({ label, value, onPick }: { label: string; value: { id: string; name: string } | null; onPick: (s: { id: string; name: string }) => void }) {
  const [text, setText] = useState("");
  const [hits, setHits] = useState<{ id: string; name: string; boardable: boolean }[]>([]);
  useEffect(() => {
    if (text.trim().length < 2) { setHits([]); return; }
    const t = setTimeout(() => api.region.search(text.trim()).then(setHits).catch(() => setHits([])), 150);
    return () => clearTimeout(t);
  }, [text]);
  return (
    <div className="picker">
      <label>
        <span>{label}</span>
        <input value={text || value?.name || ""} onChange={(e) => setText(e.target.value)} onFocus={() => setText(value?.name || " ")}
               placeholder="Type a station name" aria-autocomplete="list" />
      </label>
      {hits.length > 0 && (
        <ul className="matches" role="listbox" aria-label={`${label} — matching stations`}>
          {hits.map((h) => (
            <li key={h.id}><button role="option" aria-selected={value?.id === h.id} onClick={() => { onPick(h); setText(""); setHits([]); }}>
              {h.name} {!h.boardable && <small>no boardable platform</small>}</button></li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function RegionView({ onOpenStation, onError, region, regions, onRegion }: { onOpenStation: (sncfStationId: string) => void; onError: (m: string) => void;
  region: string; regions: RegionInfo[]; onRegion: (code: string) => void }) {
  const [view, setView] = useState<RegionViewName>("best");
  const [ov, setOv] = useState<RegionOverview | null>(null);
  const [stations, setStations] = useState<RegionStation[]>([]);
  const [rank, setRank] = useState<RegionRank | null>(null);
  const [rec, setRec] = useState<Reconciliation | null>(null);
  const [tab, setTab] = useState<"repairs" | "stale" | "missing">("repairs");
  const [from, setFrom] = useState<{ id: string; name: string } | null>(null);
  const [to, setTo] = useState<{ id: string; name: string } | null>(null);
  const [journeys, setJourneys] = useState<Partial<Record<RegionViewName, Journey>>>({});
  const [selected, setSelected] = useState<string | null>(null);
  const [stationOut, setStationOut] = useState<{ station: { id: string; name: string }; outages: OutageDetail[];
    lifts?: { id: string; operator: string; status: string; updated: string | null; direction: string | null; reported_by_prim: boolean; lines: string[] }[] } | null>(null);
  const [busy, setBusy] = useState<string | null>("Computing step-free journeys across the region…");
  const [reach, setReach] = useState<Reach | null>(null);
  const [compare, setCompare] = useState<RegionCompareRow[] | null>(null);
  const toggleCompare = () => {
    if (compare) { setCompare(null); return; }
    api.regionsCompare().then((r) => setCompare(r.regions)).catch(fail);
  };
  const fail = (e: unknown) => onError(e instanceof ApiError ? e.message : String(e));

  useEffect(() => {
    Promise.all([api.region.overview(), api.region.rank(), api.region.reconciliation()])
      .then(([o, r, c]) => { setOv(o); setRank(r); setRec(c); })
      .catch(fail).finally(() => setBusy(null));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { api.region.map(view).then((m) => setStations(m.stations)).catch(fail); }, [view]); // eslint-disable-line

  useEffect(() => {
    if (!selected) { setStationOut(null); setReach(null); return; }
    api.region.stationOutages(selected, view).then(setStationOut).catch(fail);
    api.region.reach(selected, view).then((r) => setReach(r.origin_boardable ? r : null)).catch(fail);
  }, [selected, view]); // eslint-disable-line

  const check = async (a = from, b = to) => {
    if (!a || !b) return;
    setBusy("Searching the network graph…");
    try {
      const [best, feed, published] = await Promise.all((["best", "feed", "published"] as RegionViewName[]).map((v) => api.region.journey(a.id, b.id, v)));
      setJourneys({ best, feed, published });
      setSelected(null);
      setReach(null);
    } catch (e) { fail(e); } finally { setBusy(null); }
  };

  const j = journeys[view] || null;
  const v = ov?.views[view];
  const pub = ov?.views.published;
  const VIEWS: RegionViewName[] = ov && !ov.has_feed ? ["best", "published"] : ["best", "feed", "published"];
  const isDefault = !!regions.find((r) => r.code === region)?.default;
  const examples = EXAMPLES[region] || [];
  const help = (x: RegionViewName) => (x === "best" && ov && !ov.idfm_status ? "SNCF's hourly lift status, read on station lift graphs" : VIEW_HELP[x]);
  const usage = ov?.entries_source?.key === "sncf_frequentation" ? "passengers a day" : "validations a day";
  const selectedStation = useMemo(() => stations.find((s) => s.id === selected) || null, [stations, selected]);

  return (
    <div className="region">
      <div className="rhead">
        {regions.length > 1 && (
          <label className="regionpick">Region{" "}
            <select value={region} onChange={(e) => onRegion(e.target.value)}>
              {regions.map((r) => <option key={r.code} value={r.code}>{r.name} — {r.network_label}</option>)}
            </select>
          </label>
        )}
        {regions.length > 2 && (
          <button className="ghost small" aria-expanded={!!compare} onClick={toggleCompare}>{compare ? "Hide the comparison" : "Compare all regions"}</button>
        )}
        <div className="viewswitch light" role="tablist" aria-label="Which lift status to believe">
          {VIEWS.map((x) => (
            <button key={x} role="tab" aria-selected={view === x} className={view === x ? "on" : ""} onClick={() => setView(x)} title={help(x)}>{VIEW_LABEL[x]}</button>
          ))}
        </div>
        <p className="muted small">{help(view)}.</p>
      </div>

      <aside className="left">
        <section className="journey" aria-labelledby="jh">
          <h2 id="jh">Can I get there in a wheelchair?</h2>
          <StationPicker label="From" value={from} onPick={(s) => { setFrom(s); if (to) check(s, to); }} />
          <StationPicker label="To" value={to} onPick={(s) => { setTo(s); if (from) check(from, s); }} />
          <div className="report-actions">
            <button className="primary small" disabled={!from || !to} onClick={() => check()}>Check the journey</button>
            <span className="muted small">or try:</span>
          </div>
          <div className="chips">
            {examples.map(([a, an, b, bn]) => (
              <button key={a + b} className="chip" onClick={() => { const A = { id: a, name: an }, B = { id: b, name: bn }; setFrom(A); setTo(B); check(A, B); }}>{an} → {bn}</button>
            ))}
          </div>
          {j && (
            <div className={`jresult ${VERDICT[j.verdict].cls}`} aria-live="polite">
              <p className="jverdict">{VERDICT[j.verdict].title}</p>
              <p className="small">{j.from.name} → {j.to.name}, {VIEW_PHRASE[view]}</p>
              {j.reason && <p className="small">{j.reason}</p>}
              {j.legs.length > 0 && (
                <ol className="legs">
                  {j.legs.map((l, i) => (
                    <li key={i}>
                      <LineBadge name={l.line_name} color={l.color} text={l.text_color} />
                      <span>{l.from_name} <span className={`pst s-${l.board_state}`}>{STATE_WORD[l.board_state]}</span>
                        {" → "}{l.to_name} <span className={`pst s-${l.alight_state}`}>{STATE_WORD[l.alight_state]}</span></span>
                    </li>
                  ))}
                </ol>
              )}
              {!!j.blocking_outages?.length && (
                <details>
                  <summary>{j.blocking_outages.length} lift outage{j.blocking_outages.length > 1 ? "s" : ""} listed on this route</summary>
                  <ul className="olist">
                    {j.blocking_outages.map((o, i) => (
                      <li key={i}><strong>{o.station}</strong> — {o.text || o.name}
                        {o.first_reported && <span className="muted"> · listed since {date(o.first_reported)}</span>}</li>
                    ))}
                  </ul>
                </details>
              )}
              <div className="jcompare">
                {VIEWS.filter((x) => x !== view).map((x) => journeys[x] && (
                  <button key={x} className={`mini ${VERDICT[journeys[x]!.verdict].cls}`} onClick={() => setView(x)}>
                    {VIEW_LABEL[x]}: {VERDICT[journeys[x]!.verdict].title.toLowerCase()}
                  </button>
                ))}
              </div>
              <p className="muted tiny">{j.verification.ok ? `Every leg re-checked in Relate${STATIC_DEMO ? " (WebAssembly, in this browser)" : ""} (${j.verification.verified}/${j.verification.legs}): boardable platforms of the stated stations joined by a LEG of that line.` : "Leg verification failed — do not rely on this route."}</p>
            </div>
          )}
        </section>

        <TripWatch region={region} journey={journeys.best || null} onError={onError} />

        {selectedStation && (
          <section className="stationcard" aria-live="polite">
            <div className="sc-head">
              <h3>{selectedStation.name}</h3>
              <button className="ghost dark small" onClick={() => setSelected(null)}>Close</button>
            </div>
            {selectedStation.entries_per_day != null && (
              <p className="muted tiny">≈ {n(selectedStation.entries_per_day)} {ov?.entries_source?.key === "sncf_frequentation" ? "passengers a day (2025 yearly total ÷ 365, SNCF)" : "ticket validations a day (all riders, Apr–Jun 2026)"}</p>
            )}
            {reach && reach.origin.id === selectedStation.id && (
              <div className="reachbox" aria-live="polite">
                <p className="reach-num">{n(reach.counts.confirmed)}</p>
                <p className="reach-cap">stations reachable step-free from here, {VIEW_PHRASE[view]}</p>
                <ul className="reach-legend">
                  <li><i className="dot green" />{n(reach.counts.confirmed)} confirmed</li>
                  <li><i className="dot amber" />{n(reach.counts.if_lifts_work)} only if listed lifts work</li>
                  <li><i className="dot red" />{n(reach.counts.cut)} cut by outages (reachable in the published network)</li>
                </ul>
                <p className="muted tiny">Those confirmed stations see ≈ {n(reach.entries_per_day.confirmed)} validations a day; the cut ones ≈ {n(reach.entries_per_day.cut)}.</p>
                <p className="muted tiny">{reach.verification.ok ? `Re-derived in Relate${STATIC_DEMO ? " (WebAssembly, in this browser)" : ""} with Cypher (${reach.verification.rounds} breadth-first rounds over HAS_PLATFORM/LEG, ${reach.verification.ms} ms): ${reach.verification.cypher} = ${reach.verification.engine}.` : `Cypher re-derivation disagrees (${reach.verification.cypher} vs ${reach.verification.engine}) — do not rely on this number.`}</p>
              </div>
            )}
            <p className="small">{selectedStation.state === "NOT_BOARDABLE" ? "No platform declared wheelchair-boardable in GTFS / IDFM data." :
              selectedStation.state === "OPEN" ? "All boardable platforms open in this view." :
              selectedStation.state === "DOUBT" ? "A listed lift outage concerns a boardable platform here; UNLOCK can't tell if another lift serves it." :
              "UNLOCK's station topology shows no platform keeps a confirmed step-free route to the street."}</p>
            {!!stationOut?.lifts?.length && (
              <details className="liftlist" open={stationOut.lifts.some((l) => l.status !== "AVAILABLE")}>
                <summary>{stationOut.lifts.length} lift{stationOut.lifts.length > 1 ? "s" : ""} in {ov?.idfm_status ? "IDFM's" : "SNCF's hourly"} lift status — {stationOut.lifts.filter((l) => l.status === "UNAVAILABLE").length} out of service</summary>
                <ul className="olist">
                  {stationOut.lifts.map((l) => (
                    <li key={l.id}><span className={`pst s-${l.status === "AVAILABLE" ? "OPEN" : l.status === "UNAVAILABLE" ? "CLOSED" : "DOUBT"}`}>{l.status === "AVAILABLE" ? "working" : l.status === "UNAVAILABLE" ? "out of service" : "unknown"}</span>{" "}
                      {l.direction || l.id} <span className="muted tiny">· {l.operator} · updated {l.updated || "—"}{l.reported_by_prim ? " · also in PRIM" : ""}</span></li>
                  ))}
                </ul>
              </details>
            )}
            {view === "best" && !!stationOut?.outages.length && (
              <p className="muted tiny">This view reads lift status from SNCF's and IDFM's status datasets; the PRIM messages below are shown for comparison.</p>
            )}
            {stationOut?.outages.length ? (
              <ul className="olist">
                {stationOut.outages.map((o) => (
                  <li key={o.id}>
                    <p>{o.text}</p>
                    <p className="muted tiny">{o.operator === "SNCF_GC" ? "SNCF Gares & Connexions" : o.operator} · listed since {date(o.first_reported)} ({o.days_reported} days)
                      {o.announced_until && <> · announced until {o.announced_until}</>}{o.lines.length ? <> · lines {o.lines.join(", ")}</> : null}</p>
                    {o.sncf_station_all_working != null && (
                      <p className={`tiny verdict-${o.sncf_station_all_working ? "AVAILABLE" : "UNKNOWN"}`}>Not matched to a single lift — SNCF's hourly feed: <strong>{o.sncf_station_all_working ? "every lift at this station reported working" : "at least one lift here not reported working"}</strong></p>
                    )}
                    {o.matched_lifts.map((m) => (
                      <p key={m.id} className={`tiny verdict-${m.sncf_state}`}>Matched to <strong>{m.name}</strong> — SNCF's hourly feed says: <strong>{m.sncf_state === "AVAILABLE" ? "working" : m.sncf_state === "UNAVAILABLE" ? "out of service" : "unknown"}</strong></p>
                    ))}
                  </li>
                ))}
              </ul>
            ) : <p className="muted small">The PRIM feed lists no lift outage here.</p>}
            {isDefault && !STATIC_DEMO && selectedStation.sncf_station && selectedStation.detail && (
              <button className="primary small" onClick={() => onOpenStation(selectedStation.sncf_station!)}>Open inside the station →</button>
            )}
          </section>
        )}
      </aside>

      <main className="center">
        {compare && (
          <section className="compare" aria-labelledby="cmph">
            <h2 id="cmph">Every region, same method</h2>
            <p className="small muted">Ordered station pairs joined by a step-free journey, published vs confirmed with today's lift status. Île-de-France uses richer sources (IDFM GTFS and lift status); the other regions use national SNCF data only, so compare them with each other first.</p>
            <div className="cmp-scroll">
              <table>
                <thead><tr><th scope="col">Region</th><th scope="col">Accessible stations</th><th scope="col">Published</th><th scope="col">Confirmed today</th><th scope="col">Share</th><th scope="col">SNCF lifts out / unknown</th><th scope="col">Stations with a modelled lift route to the street</th></tr></thead>
                <tbody>
                  {compare.map((r) => (
                    <tr key={r.code} className={r.code === region ? "on" : ""}>
                      <th scope="row"><button className="linkish" onClick={() => onRegion(r.code)}>{r.name}</button></th>
                      <td>{n(r.accessible_stations)}</td><td>{n(r.published)}</td><td>{n(r.confirmed)}</td>
                      <td><span className="cmp-bar"><span style={{ width: `${Math.round((r.share_confirmed ?? 0) * 100)}%` }} /></span> {r.share_confirmed == null ? "—" : `${(r.share_confirmed * 100).toFixed(1)} %`}</td>
                      <td>{n(r.sncf_lifts_out)} / {n(r.sncf_lifts_unknown)}{r.ratp_lifts_out != null ? ` (+${n(r.ratp_lifts_out)} RATP)` : ""}</td>
                      <td>{n(r.with_platform_exit_topology)} of {n(r.accessible_stations_with_lifts)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="tiny muted">Where the lift text gives no platform↔street route, a lift not reported working puts the station in doubt — it is never assumed harmless. Status read: {compare[0]?.sncf_status_observed_at?.slice(0, 16).replace("T", " ")} UTC.</p>
          </section>
        )}
        {ov && v && pub && (
          <section className="headline" aria-label="Region-wide step-free journeys">
            <div className="hl-main">
              <p className="hl-num">{n(v.confirmed)}</p>
              <p className="hl-cap">step-free station-to-station journeys confirmed in {ov.region.name} {VIEW_PHRASE[view]}</p>
              <p className="small muted">{n(pub.confirmed)} published between {n(ov.network.stations_with_boardable_platform)} stations
                {v.possible > v.confirmed && <> · {n(v.possible - v.confirmed)} more only if every listed lift works</>}</p>
            </div>
            <div className="hl-bars" aria-label="Confirmed journeys by view">
              {(["published", "best", "feed"] as RegionViewName[]).filter((x) => VIEWS.includes(x)).map((x) => (
                <button key={x} className={`hl-bar ${x === view ? "on" : ""}`} onClick={() => setView(x)}>
                  <span className="hb-label">{VIEW_LABEL[x]}</span>
                  <span className="hb-track"><span className={`hb-fill hb-${x}`} style={{ width: `${(100 * ov.views[x].confirmed) / pub.confirmed}%` }} /></span>
                  <span className="hb-val">{n(ov.views[x].confirmed)}</span>
                </button>
              ))}
            </div>
          </section>
        )}
        {ov && view === "best" && <HistoryChart />}
        {ov?.feed && ov.stale_messages && (
          <section className="frozen" aria-label="Outage feed quality">
            <p><strong>The regional lift-outage feed has stopped moving.</strong> PRIM still lists {n(ov.outages.lifts)} lifts as out of service
              ({n(ov.outages.messages)} messages); none of them changed since {date(ov.feed.last_lift_update)} — {ov.feed.lift_messages_stale_days} days — while
              other traffic messages were updated {date(ov.feed.last_other_update)}.</p>
            <p>SNCF's own hourly feed contradicts {n(ov.reconciliation.GHOST + ov.reconciliation.UNRESOLVED_STATION_ALL_WORKING)} of the {n(ov.outages.by_operator.SNCF_GC)} SNCF lifts it lists.
              Those stale messages alone hide <strong>{n(ov.stale_messages.journeys_hidden)}</strong> step-free journeys.</p>
            {!!ov.idfm_status?.night_closure_suspected && (
              <p><strong>Night snapshot.</strong> IDFM's lift status was read at {ov.idfm_status.observed_paris?.slice(11)} (Paris): {n(ov.idfm_status.night_closure_suspected)} RATP lifts switched off since 23:00 are treated as <em>unknown</em> (end-of-service shutdown), not as outages.</p>
            )}
            {(ov.reconciliation.RATP_GHOST ?? 0) > 0 && (
              <p>IDFM's own lift-status dataset (refreshed several times a day) also contradicts {n(ov.reconciliation.RATP_GHOST)} of the {n((ov.reconciliation.RATP_GHOST ?? 0) + (ov.reconciliation.RATP_CONFIRMED ?? 0) + (ov.reconciliation.RATP_UNCLEAR ?? 0))} RATP messages UNLOCK can match to a lift.</p>
            )}
            {ov.feed_watch && ov.feed_watch.observations > 1 && (
              <p className="tiny">UNLOCK fetched the feed {ov.feed_watch.observations} times between {stamp(ov.feed_watch.first_observed)} and {stamp(ov.feed_watch.last_observed)}:
                the lift content was {ov.feed_watch.all_identical ? "identical every time" : `identical in the last ${ov.feed_watch.identical_lift_content}`} (same hash of all {n(ov.outages.messages)} messages).</p>
            )}
          </section>
        )}
        <RegionMap center={ov?.region.center} zoom={ov?.region.zoom} label={ov ? `${ov.region.name} — ${ov.region.network_label}` : undefined} stations={stations} reach={reach && !j ? { origin: reach.origin.id, classes: reach.classes } : null}
                   journey={j} selected={selected} onSelect={(id) => { setJourneys({}); setSelected(id); }} />
        {reach && !j ? (
          <div className="legend region-legend" aria-label="Map legend — step-free reach">
            <span><b>From {reach.origin.name}:</b></span>
            <span><i className="dot green" />Reachable step-free</span>
            <span><i className="dot amber" />Only if listed lifts work</span>
            <span><i className="dot red" />Cut by outages</span>
            <span><i className="dot grey" />No step-free route / not boardable</span>
          </div>
        ) : (
          <div className="legend region-legend" aria-label="Map legend">
            <span><i className="dot ink" />Boardable, open</span>
            <span><i className="dot amber" />Lift listed out — not confirmed</span>
            <span><i className="dot red" />Cut off (station topology)</span>
            <span><i className="dot grey" />No boardable platform</span>
            <span className="muted">Click a station to see where you can go from it.</span>
          </div>
        )}
        {busy && <p className="busy" role="status">{busy}</p>}
      </main>

      <aside className="right">
        <div className="rtabs" role="tablist" aria-label="Region lists">
          <button role="tab" aria-selected={tab === "repairs"} className={tab === "repairs" ? "on" : ""} onClick={() => setTab("repairs")}>Repairs that matter</button>
          {ov?.has_feed !== false && <>
          <button role="tab" aria-selected={tab === "stale"} className={tab === "stale" ? "on" : ""} onClick={() => setTab("stale")}>Stale messages</button>
          <button role="tab" aria-selected={tab === "missing"} className={tab === "missing" ? "on" : ""} onClick={() => setTab("missing")}>Not in the feed</button>
          </>}
        </div>
        {tab === "repairs" && rank && (
          <section aria-label="Repairs ranked by journeys given back">
            <p className="small">Fix one lift, give back this many confirmed step-free journeys (best available status). Equal gains: busiest station first.</p>
            <p className="small"><a href={bulletinUrl(region, isDefault)} target="_blank" rel="noopener">Today's maintenance bulletin (printable)</a></p>
            <ol className="rank">
              {rank.repairs.map((r) => (
                <li key={r.outage || r.lift}>
                  <button onClick={() => setSelected((r.kind === "SNCF_LIFT" ? r.region_station_id : r.station_id) || null)}>
                    <span className="gain">+{n(r.gain)}</span>
                    <span className="rbody"><span className="rwho"><strong>{r.station}</strong>{r.lines?.map((l) => <span key={l} className="tag">{l}</span>)}</span>
                      <span className="small clamp">{r.kind === "SNCF_LIFT" ? `${r.name} — out of service in SNCF's hourly feed` : r.kind === "RATP_LIFT" || r.kind === "RATP_LIFT_CHECK" ? `${r.name} — ${r.status_note === "NIGHT_CLOSURE_SUSPECTED" ? "switched off for the night — check in the morning" : r.state === "UNKNOWN" ? "status unknown — check on site" : "out of service"} in IDFM's lift status` : r.text}</span>
                      {r.entries_per_day != null && <span className="muted tiny">≈ {n(r.entries_per_day)} {usage} at this station</span>}
                      {r.first_reported && <span className="muted tiny">listed since {date(r.first_reported)} ({days(r.first_reported)} days){r.kind === "RATP_FEED_OUTAGE" ? " · RATP, PRIM feed only — check on site" : ""}</span>}
                    </span>
                  </button>
                </li>
              ))}
            </ol>
          </section>
        )}
        {tab === "stale" && rec && rank && (
          <section aria-label="Feed messages contradicted by SNCF">
            <p className="small">PRIM lists these SNCF lifts as broken; SNCF's hourly feed says they work. Correcting a message gives back journeys for free.</p>
            <ol className="rank">
              {rank.corrections.filter((c) => c.gain > 0).map((c) => (
                <li key={c.outage}><button onClick={() => { setView("feed"); setSelected(c.station_id || null); }}>
                  <span className="gain">+{n(c.gain)}</span>
                  <span className="rbody"><strong>{c.station}</strong><span className="small clamp">{c.text}</span>
                    <span className="muted tiny">{c.verdict === "GHOST" ? "matched to one SNCF lift reported working" : "every SNCF lift at this station reported working"} · listed since {date(c.first_reported)}</span></span>
                </button></li>
              ))}
            </ol>
            <p className="muted tiny">{n(rec.counts.GHOST)} messages matched to a lift SNCF reports working · {n(rec.counts.UNRESOLVED_STATION_ALL_WORKING)} at stations where every SNCF lift works · {n(rec.counts.CONFIRMED)} confirmed by SNCF · {n(rec.counts.UNRESOLVED)} unresolved.</p>
          </section>
        )}
        {tab === "missing" && rec && (
          <section aria-label="Lifts out of service but absent from the feed">
            <p className="small">Out of service in SNCF's hourly feed, absent from the PRIM feed — invisible to apps built on it.</p>
            <ul className="olist">
              {rec.missing_from_feed.map((m) => <li key={m.lift}><strong>{m.station}</strong> — {m.name}</li>)}
            </ul>
          </section>
        )}
        {ov && <p className="muted tiny method">{ov.method} Computed in {ov.computed_ms} ms.</p>}
      </aside>
    </div>
  );
}
