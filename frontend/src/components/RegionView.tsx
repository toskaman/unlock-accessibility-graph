import { useEffect, useMemo, useState } from "react";
import { api, ApiError, bulletinUrl, STATIC_DEMO } from "../api";
import type { RegionCompareRow, RegionInfo, Journey, OutageDetail, Reach, Reconciliation, RegionOverview, RegionRank, RegionStation, RegionViewName } from "../types";
import { TripWatch } from "./TripWatch";
import { HistoryChart } from "./HistoryChart";
import { LiftHistory } from "./LiftHistory";
import { Intro } from "./Intro";
import { RegionMap } from "./RegionMap";
import { FieldReports } from "./FieldReports";
import { AgentReplay } from "./AgentReplay";
import { fmtDate, fmtDay, isFr, netLabel, num, pl, tr } from "../i18n";

const VIEW_LABEL = (v: RegionViewName) => ({
  best: tr("Best available status", "Meilleur état connu"),
  feed: tr("PRIM outage feed", "Flux de pannes PRIM"),
  published: tr("Published network", "Réseau publié"),
})[v];
const VIEW_HELP = (v: RegionViewName) => ({
  best: tr("SNCF's hourly lift status + IDFM's lift status for RATP (refreshed several times a day), both read on station lift graphs",
    "État horaire des ascenseurs SNCF + état des ascenseurs RATP publié par IDFM (mis à jour plusieurs fois par jour), lus sur le plan des ascenseurs de chaque gare"),
  feed: tr("Every lift outage listed in the PRIM traffic-information feed", "Toutes les pannes d'ascenseur listées dans le flux d'information trafic PRIM"),
  published: tr("Platforms declared wheelchair-boardable, no outage at all", "Quais déclarés accessibles en fauteuil, sans aucune panne"),
})[v];
const VIEW_PHRASE = (v: RegionViewName) => ({
  best: tr("with the best available lift status", "avec le meilleur état connu des ascenseurs"),
  feed: tr("according to the PRIM outage feed", "d'après le flux de pannes PRIM"),
  published: tr("in the published network, ignoring outages", "dans le réseau publié, sans tenir compte des pannes"),
})[v];
const VERDICT_CLS: Record<Journey["verdict"], string> = {
  STEP_FREE: "v-ok", STEP_FREE_IF_LIFTS_WORK: "v-doubt", CUT_BY_OUTAGES: "v-cut", NO_STEP_FREE_ROUTE_PUBLISHED: "v-none",
};
const VERDICT = (v: Journey["verdict"]) => ({ cls: VERDICT_CLS[v], title: ({
  STEP_FREE: tr("Step-free journey", "Trajet sans marche"),
  STEP_FREE_IF_LIFTS_WORK: tr("Possible only if listed lifts work", "Possible seulement si les ascenseurs signalés fonctionnent"),
  CUT_BY_OUTAGES: tr("Cut by reported outages", "Coupé par des pannes signalées"),
  NO_STEP_FREE_ROUTE_PUBLISHED: tr("No step-free route in the published network", "Aucun trajet sans marche dans le réseau publié"),
})[v] });
const STATE_WORD = (x: "OPEN" | "DOUBT" | "CLOSED") => ({
  OPEN: tr("open", "ouvert"), DOUBT: tr("lift listed out", "ascenseur signalé en panne"), CLOSED: tr("cut off", "coupé"),
})[x];
const STATUS_WORD = (x: string) => (x === "AVAILABLE" ? tr("working", "en service") : x === "UNAVAILABLE" ? tr("out of service", "hors service") : tr("unknown", "inconnu"));
const OPERATOR = (o: string) => (o === "SNCF_GC" ? "SNCF Gares & Connexions" : o);
const EXAMPLES: Record<string, [string, string, string, string][]> = {
  idf: [["73798", "Rosa Parks", "478505", "Juvisy"], ["65582", "Garges - Sarcelles", "71410", "Gare du Nord"]],
  ara: [["OCE87721175", "Lyon Gorge de Loup", "OCE87723197", "Lyon Part Dieu"], ["OCE87747006", "Grenoble", "OCE87722587", "Vienne"]],
};
const n = num;
const date = (s?: string | null) => (s ? fmtDay(new Date(s.length <= 19 ? s + "Z" : s), { day: "numeric", month: "short", year: "numeric" }) : "—");
const stamp = (s?: string | null) => (s ? fmtDate(new Date(s), { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "UTC" }) + " UTC" : "—");
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
               placeholder={tr("Type a station name", "Tapez un nom de gare")} aria-autocomplete="list" />
      </label>
      {hits.length > 0 && (
        <ul className="matches" role="listbox" aria-label={`${label} — ${tr("matching stations", "gares correspondantes")}`}>
          {hits.map((h) => (
            <li key={h.id}><button role="option" aria-selected={value?.id === h.id} onClick={() => { onPick(h); setText(""); setHits([]); }}>
              {h.name} {!h.boardable && <small>{tr("no boardable platform", "aucun quai accessible")}</small>}</button></li>
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
  const [tab, setTab] = useState<"repairs" | "stale" | "missing" | "history">("repairs");
  const [frame, setFrame] = useState<Record<string, string> | null>(null);
  const [from, setFrom] = useState<{ id: string; name: string } | null>(null);
  const [to, setTo] = useState<{ id: string; name: string } | null>(null);
  const [journeys, setJourneys] = useState<Partial<Record<RegionViewName, Journey>>>({});
  const [selected, setSelected] = useState<string | null>(null);
  const [stationOut, setStationOut] = useState<{ station: { id: string; name: string }; outages: OutageDetail[];
    lifts?: { id: string; operator: string; status: string; updated: string | null; direction: string | null; name?: string | null; reported_by_prim: boolean; lines: string[] }[] } | null>(null);
  const [busy, setBusy] = useState<string | null>(() => tr("Computing step-free journeys across the region…", "Calcul des trajets sans marche dans toute la région…"));
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
    setBusy(tr("Searching the network graph…", "Recherche dans le graphe du réseau…"));
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
  const help = (x: RegionViewName) => (x === "best" && ov && !ov.idfm_status ? tr("SNCF's hourly lift status, read on station lift graphs", "État horaire des ascenseurs SNCF, lu sur le plan des ascenseurs de chaque gare") : VIEW_HELP(x));
  const usage = ov?.entries_source?.key === "sncf_frequentation" ? tr("passengers a day", "voyageurs par jour") : tr("validations a day", "validations par jour");
  const selectedStation = useMemo(() => stations.find((s) => s.id === selected) || null, [stations, selected]);

  return (
    <div className="region">
      <div className="rhead">
        {regions.length > 1 && (
          <label className="regionpick">{tr("Region", "Région")}{" "}
            <select value={region} onChange={(e) => onRegion(e.target.value)}>
              {regions.map((r) => <option key={r.code} value={r.code}>{r.name} — {netLabel(r.network_label)}</option>)}
            </select>
          </label>
        )}
        {regions.length > 2 && (
          <button className="ghost small" aria-expanded={!!compare} onClick={toggleCompare}>{compare ? tr("Hide the comparison", "Masquer la comparaison") : tr("Compare all regions", "Comparer toutes les régions")}</button>
        )}
        <div className="viewswitch light" role="tablist" aria-label={tr("Which lift status to believe", "Quel état des ascenseurs croire")}>
          {VIEWS.map((x) => (
            <button key={x} role="tab" aria-selected={view === x} className={view === x ? "on" : ""} onClick={() => setView(x)} title={help(x)}>{VIEW_LABEL(x)}</button>
          ))}
        </div>
        <p className="muted small">{help(view)}.</p>
      </div>

      <aside className="left">
        <section className="journey" aria-labelledby="jh">
          <h2 id="jh">{tr("Can I get there in a wheelchair?", "Puis-je y aller en fauteuil ?")}</h2>
          <StationPicker label={tr("From", "Départ")} value={from} onPick={(s) => { setFrom(s); if (to) check(s, to); }} />
          <StationPicker label={tr("To", "Arrivée")} value={to} onPick={(s) => { setTo(s); if (from) check(from, s); }} />
          <div className="report-actions">
            <button className="primary small" disabled={!from || !to} onClick={() => check()}>{tr("Check the journey", "Vérifier le trajet")}</button>
            <span className="muted small">{tr("or try:", "ou essayez :")}</span>
          </div>
          <div className="chips">
            {examples.map(([a, an, b, bn]) => (
              <button key={a + b} className="chip" onClick={() => { const A = { id: a, name: an }, B = { id: b, name: bn }; setFrom(A); setTo(B); check(A, B); }}>{an} → {bn}</button>
            ))}
          </div>
          {j && (
            <div className={`jresult ${VERDICT(j.verdict).cls}`} aria-live="polite">
              <p className="jverdict">{VERDICT(j.verdict).title}</p>
              <p className="small">{j.from.name} → {j.to.name}, {VIEW_PHRASE(view)}</p>
              {j.reason && <p className="small">{isFr() ? "Ces deux gares ne sont pas reliées par des quais accessibles dans le réseau publié (ou l'une n'a aucun quai déclaré accessible en fauteuil)." : j.reason}</p>}
              {j.legs.length > 0 && (
                <ol className="legs">
                  {j.legs.map((l, i) => (
                    <li key={i}>
                      <LineBadge name={l.line_name} color={l.color} text={l.text_color} />
                      <span>{l.from_name} <span className={`pst s-${l.board_state}`}>{STATE_WORD(l.board_state)}</span>
                        {" → "}{l.to_name} <span className={`pst s-${l.alight_state}`}>{STATE_WORD(l.alight_state)}</span></span>
                    </li>
                  ))}
                </ol>
              )}
              {!!j.blocking_outages?.length && (
                <details>
                  <summary>{isFr() ? `${j.blocking_outages.length} ${pl(j.blocking_outages.length, "panne")} d'ascenseur ${pl(j.blocking_outages.length, "signalée")} sur ce trajet` : `${j.blocking_outages.length} lift outage${j.blocking_outages.length > 1 ? "s" : ""} listed on this route`}</summary>
                  <ul className="olist">
                    {j.blocking_outages.map((o, i) => (
                      <li key={i}><strong>{o.station}</strong> — {o.text || o.name}
                        {o.first_reported && <span className="muted"> · {tr("listed since", "signalée depuis le")} {date(o.first_reported)}</span>}</li>
                    ))}
                  </ul>
                </details>
              )}
              <div className="jcompare">
                {VIEWS.filter((x) => x !== view).map((x) => journeys[x] && (
                  <button key={x} className={`mini ${VERDICT(journeys[x]!.verdict).cls}`} onClick={() => setView(x)}>
                    {VIEW_LABEL(x)} : {VERDICT(journeys[x]!.verdict).title.toLowerCase()}
                  </button>
                ))}
              </div>
              <p className="muted tiny">{j.verification.ok
                ? tr(`Every leg re-checked in Relate${STATIC_DEMO ? " (WebAssembly, in this browser)" : ""} (${j.verification.verified}/${j.verification.legs}): boardable platforms of the stated stations joined by a LEG of that line.`,
                     `Chaque tronçon revérifié dans Relate${STATIC_DEMO ? " (WebAssembly, dans ce navigateur)" : ""} (${j.verification.verified}/${j.verification.legs}) : quais accessibles des gares indiquées reliés par cette ligne.`)
                : tr("Leg verification failed — do not rely on this route.", "La vérification d'un tronçon a échoué : ne vous fiez pas à ce trajet.")}</p>
            </div>
          )}
        </section>

        <TripWatch region={region} journey={journeys.best || null} onError={onError} />

        {selectedStation && (
          <section className="stationcard" aria-live="polite">
            <div className="sc-head">
              <h3>{selectedStation.name}</h3>
              <button className="ghost dark small" onClick={() => setSelected(null)}>{tr("Close", "Fermer")}</button>
            </div>
            {selectedStation.entries_per_day != null && (
              <p className="muted tiny">≈ {n(selectedStation.entries_per_day)} {ov?.entries_source?.key === "sncf_frequentation" ? tr("passengers a day (2025 yearly total ÷ 365, SNCF)", "voyageurs par jour (total 2025 ÷ 365, SNCF)") : tr("ticket validations a day (all riders, Apr–Jun 2026)", "validations par jour (tous voyageurs, avril–juin 2026)")}</p>
            )}
            {reach && reach.origin.id === selectedStation.id && (
              <div className="reachbox" aria-live="polite">
                <p className="reach-num">{n(reach.counts.confirmed)}</p>
                <p className="reach-cap">{tr("stations reachable step-free from here,", "gares accessibles sans marche depuis ici,")} {VIEW_PHRASE(view)}</p>
                <ul className="reach-legend">
                  <li><i className="dot green" />{n(reach.counts.confirmed)} {tr("confirmed", "confirmées")}</li>
                  <li><i className="dot amber" />{n(reach.counts.if_lifts_work)} {tr("only if listed lifts work", "seulement si les ascenseurs signalés fonctionnent")}</li>
                  <li><i className="dot red" />{n(reach.counts.cut)} {tr("cut by outages (reachable in the published network)", "coupées par des pannes (accessibles dans le réseau publié)")}</li>
                </ul>
                <p className="muted tiny">{tr(`Those confirmed stations see ≈ ${n(reach.entries_per_day.confirmed)} validations a day; the cut ones ≈ ${n(reach.entries_per_day.cut)}.`,
                  `Les gares confirmées comptent ≈ ${n(reach.entries_per_day.confirmed)} validations par jour ; les gares coupées ≈ ${n(reach.entries_per_day.cut)}.`)}</p>
                <p className="muted tiny">{reach.verification.ok
                  ? tr(`Re-derived in Relate${STATIC_DEMO ? " (WebAssembly, in this browser)" : ""} with Cypher (${reach.verification.rounds} breadth-first rounds over HAS_PLATFORM/LEG, ${reach.verification.ms} ms): ${reach.verification.cypher} = ${reach.verification.engine}.`,
                       `Recalculé dans Relate${STATIC_DEMO ? " (WebAssembly, dans ce navigateur)" : ""} en Cypher (${reach.verification.rounds} parcours en largeur sur HAS_PLATFORM/LEG, ${reach.verification.ms} ms) : ${reach.verification.cypher} = ${reach.verification.engine}.`)
                  : tr(`Cypher re-derivation disagrees (${reach.verification.cypher} vs ${reach.verification.engine}) — do not rely on this number.`,
                       `Le recalcul en Cypher ne donne pas le même résultat (${reach.verification.cypher} contre ${reach.verification.engine}) : ne vous fiez pas à ce nombre.`)}</p>
              </div>
            )}
            <p className="small">{selectedStation.state === "NOT_BOARDABLE" ? tr("No platform declared wheelchair-boardable in GTFS / IDFM data.", "Aucun quai déclaré accessible en fauteuil dans les données GTFS / IDFM.") :
              selectedStation.state === "OPEN" ? tr("All boardable platforms open in this view.", "Tous les quais accessibles sont ouverts dans cette vue.") :
              selectedStation.state === "DOUBT" ? tr("A listed lift outage concerns a boardable platform here; UNLOCK can't tell if another lift serves it.", "Une panne d'ascenseur signalée concerne un quai accessible ici ; UNLOCK ne peut pas savoir si un autre ascenseur le dessert.") :
              tr("UNLOCK's station topology shows no platform keeps a confirmed step-free route to the street.", "D'après le plan de la gare, aucun quai ne garde un accès confirmé sans marche jusqu'à la rue.")}</p>
            {!!stationOut?.lifts?.length && (
              <details className="liftlist" open={stationOut.lifts.some((l) => l.status !== "AVAILABLE")}>
                <summary>{isFr()
                  ? `${stationOut.lifts.length} ${pl(stationOut.lifts.length, "ascenseur")} dans l'état ${ov?.idfm_status ? "IDFM" : "horaire SNCF"} des ascenseurs — ${stationOut.lifts.filter((l) => l.status === "UNAVAILABLE").length} hors service`
                  : `${stationOut.lifts.length} lift${stationOut.lifts.length > 1 ? "s" : ""} in ${ov?.idfm_status ? "IDFM's" : "SNCF's hourly"} lift status — ${stationOut.lifts.filter((l) => l.status === "UNAVAILABLE").length} out of service`}</summary>
                <ul className="olist">
                  {stationOut.lifts.map((l) => (
                    <li key={l.id}><span className={`pst s-${l.status === "AVAILABLE" ? "OPEN" : l.status === "UNAVAILABLE" ? "CLOSED" : "DOUBT"}`}>{STATUS_WORD(l.status)}</span>{" "}
                      {l.name || l.direction || l.id} <span className="muted tiny">· {l.operator} · {tr("updated", "mis à jour")} {l.updated || "—"}{l.reported_by_prim ? tr(" · also in PRIM", " · aussi dans PRIM") : ""}</span></li>
                  ))}
                </ul>
              </details>
            )}
            {stationOut && stationOut.station.id === selectedStation.id && (
              <FieldReports stationId={selectedStation.id} lifts={stationOut.lifts || []} canReport={STATIC_DEMO || isDefault} />
            )}
            {view === "best" && !!stationOut?.outages.length && (
              <p className="muted tiny">{tr("This view reads lift status from SNCF's and IDFM's status datasets; the PRIM messages below are shown for comparison.", "Cette vue lit l'état des ascenseurs dans les données de la SNCF et d'IDFM ; les messages PRIM ci-dessous sont affichés pour comparaison.")}</p>
            )}
            {stationOut?.outages.length ? (
              <ul className="olist">
                {stationOut.outages.map((o) => (
                  <li key={o.id}>
                    <p>{o.text}</p>
                    <p className="muted tiny">{OPERATOR(o.operator)} · {tr("listed since", "signalée depuis le")} {date(o.first_reported)} ({o.days_reported} {tr("days", "jours")})
                      {o.announced_until && <> · {tr("announced until", "fin annoncée le")} {o.announced_until}</>}{o.lines.length ? <> · {tr("lines", "lignes")} {o.lines.join(", ")}</> : null}</p>
                    {o.sncf_station_all_working != null && (
                      <p className={`tiny verdict-${o.sncf_station_all_working ? "AVAILABLE" : "UNKNOWN"}`}>{tr("Not matched to a single lift — SNCF's hourly feed:", "Pas rattaché à un seul ascenseur — état horaire SNCF :")} <strong>{o.sncf_station_all_working ? tr("every lift at this station reported working", "tous les ascenseurs de la gare sont signalés en service") : tr("at least one lift here not reported working", "au moins un ascenseur de la gare n'est pas signalé en service")}</strong></p>
                    )}
                    {o.matched_lifts.map((m) => (
                      <p key={m.id} className={`tiny verdict-${m.sncf_state}`}>{tr("Matched to", "Rattaché à")} <strong>{m.name}</strong> — {tr("SNCF's hourly feed says:", "l'état horaire SNCF indique :")} <strong>{STATUS_WORD(m.sncf_state)}</strong></p>
                    ))}
                  </li>
                ))}
              </ul>
            ) : <p className="muted small">{tr("The PRIM feed lists no lift outage here.", "Le flux PRIM ne signale aucune panne d'ascenseur ici.")}</p>}
            {isDefault && !STATIC_DEMO && selectedStation.sncf_station && selectedStation.detail && (
              <button className="primary small" onClick={() => onOpenStation(selectedStation.sncf_station!)}>{tr("Open inside the station →", "Voir l'intérieur de la gare →")}</button>
            )}
          </section>
        )}
        {region === "idf" && <AgentReplay onTrip={(A, B) => { setFrom(A); setTo(B); check(A, B); document.getElementById("jh")?.scrollIntoView({ behavior: "smooth", block: "start" }); }} />}
      </aside>

      <main className="center">
        <Intro />
        {compare && (
          <section className="compare" aria-labelledby="cmph">
            <h2 id="cmph">{tr("Every region, same method", "Toutes les régions, même méthode")}</h2>
            <p className="small muted">{tr("Ordered station pairs joined by a step-free journey, published vs confirmed with today's lift status. Île-de-France uses richer sources (IDFM GTFS and lift status); the other regions use national SNCF data only, so compare them with each other first.",
              "Paires de gares (dans les deux sens) reliées par un trajet sans marche : publiées, et confirmées avec l'état des ascenseurs du jour. L'Île-de-France utilise des sources plus riches (GTFS et état des ascenseurs IDFM) ; les autres régions n'ont que les données nationales SNCF : comparez-les d'abord entre elles.")}</p>
            <div className="cmp-scroll">
              <table>
                <thead><tr><th scope="col">{tr("Region", "Région")}</th><th scope="col">{tr("Accessible stations", "Gares accessibles")}</th><th scope="col">{tr("Published", "Publiés")}</th><th scope="col">{tr("Confirmed today", "Confirmés aujourd'hui")}</th><th scope="col">{tr("Share", "Part")}</th><th scope="col">{tr("SNCF lifts out / unknown", "Ascenseurs SNCF en panne / inconnus")}</th><th scope="col">{tr("Stations with a modelled lift route to the street", "Gares dont l'accès ascenseur quai–rue est modélisé")}</th></tr></thead>
                <tbody>
                  {compare.map((r) => (
                    <tr key={r.code} className={r.code === region ? "on" : ""}>
                      <th scope="row"><button className="linkish" onClick={() => onRegion(r.code)}>{r.name}</button></th>
                      <td>{n(r.accessible_stations)}</td><td>{n(r.published)}</td><td>{n(r.confirmed)}</td>
                      <td><span className="cmp-bar"><span style={{ width: `${Math.round((r.share_confirmed ?? 0) * 100)}%` }} /></span> {r.share_confirmed == null ? "—" : `${(r.share_confirmed * 100).toLocaleString(isFr() ? "fr-FR" : "en-GB", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} %`}</td>
                      <td>{n(r.sncf_lifts_out)} / {n(r.sncf_lifts_unknown)}{r.ratp_lifts_out != null ? ` (+${n(r.ratp_lifts_out)} RATP)` : ""}</td>
                      <td>{n(r.with_platform_exit_topology)} {tr("of", "sur")} {n(r.accessible_stations_with_lifts)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="tiny muted">{tr("Where the lift text gives no platform↔street route, a lift not reported working puts the station in doubt — it is never assumed harmless. Status read:",
              "Quand la description d'un ascenseur ne dit pas quel quai il relie à la rue, un ascenseur non signalé en service met la gare en doute : il n'est jamais supposé sans effet. État lu :")} {compare[0]?.sncf_status_observed_at?.slice(0, 16).replace("T", " ")} UTC.</p>
          </section>
        )}
        {ov && v && pub && (
          <section className="headline" aria-label={tr("Region-wide step-free journeys", "Trajets sans marche dans toute la région")}>
            <div className="hl-main">
              <p className="hl-num">{n(v.confirmed)}</p>
              <p className="hl-cap">{tr(`step-free station-to-station journeys confirmed in ${ov.region.name}`, `trajets de gare à gare sans marche confirmés en ${ov.region.name}`)} {VIEW_PHRASE(view)}</p>
              <p className="small muted">{tr(`${n(pub.confirmed)} published between ${n(ov.network.stations_with_boardable_platform)} stations`, `${n(pub.confirmed)} publiés entre ${n(ov.network.stations_with_boardable_platform)} gares`)}
                {v.possible > v.confirmed && <> · {tr(`${n(v.possible - v.confirmed)} more only if every listed lift works`, `${n(v.possible - v.confirmed)} de plus seulement si tous les ascenseurs signalés fonctionnent`)}</>}</p>
            </div>
            <div className="hl-bars" aria-label={tr("Confirmed journeys by view", "Trajets confirmés selon la vue")}>
              {(["published", "best", "feed"] as RegionViewName[]).filter((x) => VIEWS.includes(x)).map((x) => (
                <button key={x} className={`hl-bar ${x === view ? "on" : ""}`} onClick={() => setView(x)}>
                  <span className="hb-label">{VIEW_LABEL(x)}</span>
                  <span className="hb-track"><span className={`hb-fill hb-${x}`} style={{ width: `${(100 * ov.views[x].confirmed) / pub.confirmed}%` }} /></span>
                  <span className="hb-val">{n(ov.views[x].confirmed)}</span>
                </button>
              ))}
            </div>
          </section>
        )}
        {ov && view === "best" && <HistoryChart onFrame={setFrame} />}
        {ov?.feed && ov.stale_messages && (
          <section className="frozen" aria-label={tr("Outage feed quality", "Qualité du flux de pannes")}>
            {isFr() ? <>
            <p><strong>Le flux régional des pannes d'ascenseurs ne bouge plus.</strong> PRIM signale encore {n(ov.outages.lifts)} ascenseurs hors service
              ({n(ov.outages.messages)} messages) ; aucun n'a changé depuis le {date(ov.feed.last_lift_update)} — {ov.feed.lift_messages_stale_days} jours — alors que
              les autres messages trafic ont été mis à jour le {date(ov.feed.last_other_update)}.</p>
            <p>L'état horaire publié par la SNCF elle-même contredit {n(ov.reconciliation.GHOST + ov.reconciliation.UNRESOLVED_STATION_ALL_WORKING)} des {n(ov.outages.by_operator.SNCF_GC)} ascenseurs SNCF que PRIM signale.
              Ces messages périmés masquent à eux seuls <strong>{n(ov.stale_messages.journeys_hidden)}</strong> trajets sans marche.</p>
            </> : <>
            <p><strong>The regional lift-outage feed has stopped moving.</strong> PRIM still lists {n(ov.outages.lifts)} lifts as out of service
              ({n(ov.outages.messages)} messages); none of them changed since {date(ov.feed.last_lift_update)} — {ov.feed.lift_messages_stale_days} days — while
              other traffic messages were updated {date(ov.feed.last_other_update)}.</p>
            <p>SNCF's own hourly feed contradicts {n(ov.reconciliation.GHOST + ov.reconciliation.UNRESOLVED_STATION_ALL_WORKING)} of the {n(ov.outages.by_operator.SNCF_GC)} SNCF lifts it lists.
              Those stale messages alone hide <strong>{n(ov.stale_messages.journeys_hidden)}</strong> step-free journeys.</p>
            </>}
            {!!ov.idfm_status?.night_closure_suspected && (isFr()
              ? <p><strong>Relevé de nuit.</strong> L'état IDFM des ascenseurs a été lu à {ov.idfm_status.observed_paris?.slice(11)} (heure de Paris) : {n(ov.idfm_status.night_closure_suspected)} ascenseurs RATP éteints depuis 23 h sont comptés comme <em>inconnus</em> (arrêt de fin de service), pas comme des pannes.</p>
              : <p><strong>Night snapshot.</strong> IDFM's lift status was read at {ov.idfm_status.observed_paris?.slice(11)} (Paris): {n(ov.idfm_status.night_closure_suspected)} RATP lifts switched off since 23:00 are treated as <em>unknown</em> (end-of-service shutdown), not as outages.</p>
            )}
            {(ov.reconciliation.RATP_GHOST ?? 0) > 0 && (
              <p>{tr(`IDFM's own lift-status dataset (refreshed several times a day) also contradicts ${n(ov.reconciliation.RATP_GHOST)} of the ${n((ov.reconciliation.RATP_GHOST ?? 0) + (ov.reconciliation.RATP_CONFIRMED ?? 0) + (ov.reconciliation.RATP_UNCLEAR ?? 0))} RATP messages UNLOCK can match to a lift.`,
                `Les propres données d'IDFM sur l'état des ascenseurs (mises à jour plusieurs fois par jour) contredisent aussi ${n(ov.reconciliation.RATP_GHOST)} des ${n((ov.reconciliation.RATP_GHOST ?? 0) + (ov.reconciliation.RATP_CONFIRMED ?? 0) + (ov.reconciliation.RATP_UNCLEAR ?? 0))} messages RATP qu'UNLOCK peut rattacher à un ascenseur.`)}</p>
            )}
            {ov.feed_watch && ov.feed_watch.observations > 1 && (
              <p className="tiny">{isFr()
                ? `UNLOCK a relevé le flux ${ov.feed_watch.observations} fois entre le ${stamp(ov.feed_watch.first_observed)} et le ${stamp(ov.feed_watch.last_observed)} : le contenu des messages ascenseurs était ${ov.feed_watch.all_identical ? "identique à chaque fois" : `identique lors des ${ov.feed_watch.identical_lift_content} derniers relevés`} (même empreinte pour les ${n(ov.outages.messages)} messages).`
                : `UNLOCK fetched the feed ${ov.feed_watch.observations} times between ${stamp(ov.feed_watch.first_observed)} and ${stamp(ov.feed_watch.last_observed)}: the lift content was ${ov.feed_watch.all_identical ? "identical every time" : `identical in the last ${ov.feed_watch.identical_lift_content}`} (same hash of all ${n(ov.outages.messages)} messages).`}</p>
            )}
          </section>
        )}
        <RegionMap center={ov?.region.center} zoom={ov?.region.zoom} label={ov ? `${ov.region.name} — ${netLabel(ov.region.network_label)}` : undefined} stations={frame ? stations.map((s) => (s.state === "NOT_BOARDABLE" ? s : { ...s, state: (frame[s.id] || "OPEN") as RegionStation["state"] })) : stations} reach={reach && !j && !frame ? { origin: reach.origin.id, classes: reach.classes } : null}
                   journey={j} selected={selected} onSelect={(id) => { setJourneys({}); setSelected(id); }} />
        {reach && !j ? (
          <div className="legend region-legend" aria-label={tr("Map legend — step-free reach", "Légende de la carte — accès sans marche")}>
            <span><b>{tr(`From ${reach.origin.name}:`, `Depuis ${reach.origin.name} :`)}</b></span>
            <span><i className="dot green" />{tr("Reachable step-free", "Accessible sans marche")}</span>
            <span><i className="dot amber" />{tr("Only if listed lifts work", "Seulement si les ascenseurs signalés fonctionnent")}</span>
            <span><i className="dot red" />{tr("Cut by outages", "Coupée par des pannes")}</span>
            <span><i className="dot grey" />{tr("No step-free route / not boardable", "Pas de trajet sans marche / quai non accessible")}</span>
          </div>
        ) : (
          <div className="legend region-legend" aria-label={tr("Map legend", "Légende de la carte")}>
            <span><i className="dot ink" />{tr("Boardable, open", "Accessible, ouverte")}</span>
            <span><i className="dot amber" />{tr("Lift listed out — not confirmed", "Ascenseur signalé en panne — non confirmé")}</span>
            <span><i className="dot red" />{tr("Cut off (station topology)", "Coupée (plan de la gare)")}</span>
            <span><i className="dot grey" />{tr("No boardable platform", "Aucun quai accessible")}</span>
            <span className="muted">{tr("Click a station to see where you can go from it.", "Cliquez sur une gare pour voir où l'on peut aller depuis elle.")}</span>
          </div>
        )}
        {busy && <p className="busy" role="status">{busy}</p>}
      </main>

      <aside className="right">
        <div className="rtabs" role="tablist" aria-label={tr("Region lists", "Listes de la région")}>
          <button role="tab" aria-selected={tab === "repairs"} className={tab === "repairs" ? "on" : ""} onClick={() => setTab("repairs")}>{tr("Repairs that matter", "Réparations utiles")}</button>
          {ov?.has_feed !== false && <>
          <button role="tab" aria-selected={tab === "stale"} className={tab === "stale" ? "on" : ""} onClick={() => setTab("stale")}>{tr("Stale messages", "Messages périmés")}</button>
          <button role="tab" aria-selected={tab === "missing"} className={tab === "missing" ? "on" : ""} onClick={() => setTab("missing")}>{tr("Not in the feed", "Absentes du flux")}</button>
          </>}
          <button role="tab" aria-selected={tab === "history"} className={tab === "history" ? "on" : ""} onClick={() => setTab("history")}>{tr("History", "Historique")}</button>
        </div>
        {tab === "repairs" && rank && (
          <section aria-label={tr("Repairs ranked by journeys given back", "Réparations classées par trajets rendus")}>
            <p className="small">{tr("Fix one lift, give back this many confirmed step-free journeys (best available status). Equal gains: busiest station first.", "Réparer un seul ascenseur rend ce nombre de trajets sans marche confirmés (meilleur état connu). À gain égal : la gare la plus fréquentée d'abord.")}</p>
            <p className="small"><a href={bulletinUrl(region, isDefault, isFr() ? "fr" : "en")} target="_blank" rel="noopener">{tr("Today's maintenance bulletin (printable)", "Bulletin de maintenance du jour (à imprimer)")}</a></p>
            <ol className="rank">
              {rank.repairs.map((r) => (
                <li key={r.outage || r.lift}>
                  <button onClick={() => { setJourneys({}); setSelected((r.kind === "SNCF_LIFT" ? r.region_station_id : r.station_id) || null); }}>
                    <span className="gain">+{n(r.gain)}</span>
                    <span className="rbody"><span className="rwho"><strong>{r.station}</strong>{r.lines?.map((l) => <span key={l} className="tag">{l}</span>)}</span>
                      <span className="small clamp">{r.kind === "SNCF_LIFT" ? `${r.name} — ${tr("out of service in SNCF's hourly feed", "hors service d'après l'état horaire SNCF")}`
                        : r.kind === "RATP_LIFT" || r.kind === "RATP_LIFT_CHECK" ? `${r.name} — ${r.status_note === "NIGHT_CLOSURE_SUSPECTED" ? tr("switched off for the night — check in the morning", "éteint pour la nuit — à vérifier le matin") : r.state === "UNKNOWN" ? tr("status unknown — check on site", "état inconnu — à vérifier sur place") : tr("out of service", "hors service")} ${tr("in IDFM's lift status", "d'après l'état IDFM des ascenseurs")}` : r.text}</span>
                      {r.entries_per_day != null && <span className="muted tiny">≈ {n(r.entries_per_day)} {usage} {tr("at this station", "dans cette gare")}</span>}
                      {r.first_reported && <span className="muted tiny">{tr("listed since", "signalée depuis le")} {date(r.first_reported)} ({days(r.first_reported)} {tr("days", "jours")}){r.kind === "RATP_FEED_OUTAGE" ? tr(" · RATP, PRIM feed only — check on site", " · RATP, seulement dans le flux PRIM — à vérifier sur place") : ""}</span>}
                    </span>
                  </button>
                </li>
              ))}
            </ol>
          </section>
        )}
        {tab === "stale" && rec && rank && (
          <section aria-label={tr("Feed messages contradicted by SNCF", "Messages du flux contredits par la SNCF")}>
            <p className="small">{tr("PRIM lists these SNCF lifts as broken; SNCF's hourly feed says they work. Correcting a message gives back journeys for free.", "PRIM signale ces ascenseurs SNCF en panne ; l'état horaire SNCF les dit en service. Corriger un message rend des trajets sans rien réparer.")}</p>
            <ol className="rank">
              {rank.corrections.filter((c) => c.gain > 0).map((c) => (
                <li key={c.outage}><button onClick={() => { setView("feed"); setSelected(c.station_id || null); }}>
                  <span className="gain">+{n(c.gain)}</span>
                  <span className="rbody"><strong>{c.station}</strong><span className="small clamp">{c.text}</span>
                    <span className="muted tiny">{c.verdict === "GHOST" ? tr("matched to one SNCF lift reported working", "rattaché à un ascenseur SNCF signalé en service") : tr("every SNCF lift at this station reported working", "tous les ascenseurs SNCF de la gare sont signalés en service")} · {tr("listed since", "signalée depuis le")} {date(c.first_reported)}</span></span>
                </button></li>
              ))}
            </ol>
            <p className="muted tiny">{tr(`${n(rec.counts.GHOST)} messages matched to a lift SNCF reports working · ${n(rec.counts.UNRESOLVED_STATION_ALL_WORKING)} at stations where every SNCF lift works · ${n(rec.counts.CONFIRMED)} confirmed by SNCF · ${n(rec.counts.UNRESOLVED)} unresolved.`,
              `${n(rec.counts.GHOST)} messages rattachés à un ascenseur que la SNCF dit en service · ${n(rec.counts.UNRESOLVED_STATION_ALL_WORKING)} dans des gares où tous les ascenseurs SNCF fonctionnent · ${n(rec.counts.CONFIRMED)} confirmés par la SNCF · ${n(rec.counts.UNRESOLVED)} non résolus.`)}</p>
          </section>
        )}
        {tab === "missing" && rec && (
          <section aria-label={tr("Lifts out of service but absent from the feed", "Ascenseurs hors service absents du flux")}>
            <p className="small">{tr("Out of service in SNCF's hourly feed, absent from the PRIM feed — invisible to apps built on it.", "Hors service d'après l'état horaire SNCF, mais absents du flux PRIM : invisibles pour les applications qui s'appuient sur lui.")}</p>
            <ul className="olist">
              {rec.missing_from_feed.map((m) => <li key={m.lift}><strong>{m.station}</strong> — {m.name}</li>)}
            </ul>
          </section>
        )}
        {tab === "history" && <LiftHistory onSelect={(id) => { setJourneys({}); setSelected(id); }} />}
        {ov && <p className="muted tiny method">{isFr()
          ? `Paires de gares (dans les deux sens) reliées par un trajet sans marche (montée et descente uniquement à des quais accessibles et utilisables ; correspondances à l'intérieur d'une gare). Accessibilité exacte calculée sur le réseau GTFS stocké dans Relate. Calculé en ${ov.computed_ms} ms.`
          : `${ov.method} Computed in ${ov.computed_ms} ms.`}</p>}
      </aside>
    </div>
  );
}
