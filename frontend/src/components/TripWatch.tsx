import { useEffect, useState } from "react";
import { api } from "../api";
import type { Journey, SavedTrip, TripStatus } from "../types";
import { isFr, tr } from "../i18n";

const STATIC_DEMO = import.meta.env.VITE_STATIC === "1";
const feed = (region: string, t: SavedTrip, fmt: "rss" | "ics") =>
  `${location.origin}/api/region/trips/feed.${fmt}?${new URLSearchParams({ from: t.from.id, to: t.to.id, region }).toString()}`;
const key = (region: string) => `unlock.trips.v1.${region}`;
const load = (region: string): SavedTrip[] => { try { return JSON.parse(localStorage.getItem(key(region)) || "[]"); } catch { return []; } };
const store = (region: string, t: SavedTrip[]) => { try { localStorage.setItem(key(region), JSON.stringify(t)); } catch { /* storage unavailable: keep in memory */ } };

const WORD = (s: string): { cls: string; label: string } | undefined => ({
  OK: { cls: "v-ok", label: tr("Step-free today", "Sans marche aujourd'hui") },
  DETOUR: { cls: "v-doubt", label: tr("Detour needed", "Détour nécessaire") },
  AT_RISK: { cls: "v-doubt", label: tr("At risk", "Incertain") },
  CUT: { cls: "v-cut", label: tr("Cut today", "Coupé aujourd'hui") },
  NO_STEP_FREE_ROUTE: { cls: "v-none", label: tr("No step-free route", "Aucun trajet sans marche") },
  UNKNOWN_STATION: { cls: "v-none", label: tr("Unknown station", "Gare inconnue") },
} as Record<string, { cls: string; label: string }>)[s];

/** The alert sentence. English: as the engine wrote it. French: rebuilt from the same structured fields. */
function message(s: TripStatus): string {
  if (!isFr()) return s.message;
  if (s.status === "OK") return "Votre trajet habituel est sans marche aujourd'hui.";
  if (s.status === "NO_STEP_FREE_ROUTE") return "Aucun trajet sans marche entre ces deux gares, même dans le réseau publié.";
  if (s.status === "UNKNOWN_STATION") return "Ce trajet enregistré n'existe plus dans ce réseau.";
  const b = s.usual_blocked_at || [];
  const cut = [...new Set(b.filter((x) => x.state === "CLOSED").map((x) => x.station))].sort();
  const unsure = [...new Set(b.filter((x) => x.state !== "CLOSED").map((x) => x.station))].filter((x) => !cut.includes(x)).sort();
  const where = [cut.length ? `coupé à ${cut.join(", ")}` : "",
    unsure.length ? `incertain à ${unsure.join(", ")} (un ascenseur sur le trajet est en panne ou son état est inconnu)` : ""].filter(Boolean).join(" ; ");
  const legs = (s.alternative || []).map((l) => `${l.line_name ?? ""} ${l.board_name} → ${l.alight_name}`.trim()).join(" puis ");
  if (s.status === "DETOUR") return `Votre trajet habituel est ${where}. Détour sans marche aujourd'hui : ${legs}.`;
  if (s.status === "AT_RISK") return `Votre trajet habituel est ${where}. Le seul trajet sans marche restant dépend d'ascenseurs dont l'état est incertain : ${legs}.`;
  return `Aucun trajet sans marche aujourd'hui : votre trajet habituel est ${where}, comme tous les autres trajets.`;
}

/** Rider alerts: the rider's usual trips, kept in this browser only, re-checked against today's lift status. */
export function TripWatch({ region, journey, onError }: { region: string; journey: Journey | null; onError: (m: string) => void }) {
  const [trips, setTrips] = useState<SavedTrip[]>(() => load(region));
  const save = (t: SavedTrip[]) => store(region, t);
  const [status, setStatus] = useState<TripStatus[]>([]);

  const refresh = (list: SavedTrip[]) => {
    if (!list.length) { setStatus([]); return; }
    api.region.trips(list).then((r) => {
      setStatus(r.trips);
      const next = list.map((t, i) => ({ ...t, last_status: r.trips[i]?.status ?? t.last_status,
        usual: t.usual ?? r.trips[i]?.usual?.map(({ board, alight, line }) => ({ board, alight, line })) }));
      setTrips(next); save(next);
    }).catch((e) => onError(String(e?.message || e)));
  };
  useEffect(() => { refresh(trips); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const watched = journey && trips.some((t) => t.from.id === journey.from.id && t.to.id === journey.to.id);
  const add = () => {
    if (!journey) return;
    const next = [...trips, { from: { id: journey.from.id, name: journey.from.name }, to: { id: journey.to.id, name: journey.to.name } }].slice(-8);
    setTrips(next); save(next); refresh(next);
  };
  const remove = (i: number) => { const next = trips.filter((_, k) => k !== i); setTrips(next); save(next); setStatus(status.filter((_, k) => k !== i)); };
  const alerts = status.filter((s) => s.status !== "OK");

  return (
    <section className="tripwatch" aria-labelledby="twh">
      <h2 id="twh">{tr("My usual trips", "Mes trajets habituels")}</h2>
      {journey && !watched && (
        <button className="ghost small" onClick={add}>{tr("Watch", "Suivre")} {journey.from.name} → {journey.to.name}</button>
      )}
      {!trips.length && <p className="muted small">{tr("Check a journey, then watch it: UNLOCK re-checks it against today's lift status each time you open this page. Your trips stay in this browser.", "Vérifiez un trajet, puis suivez-le : UNLOCK le revérifie avec l'état des ascenseurs du jour à chaque ouverture de cette page. Vos trajets restent dans ce navigateur.")}</p>}
      {!!alerts.length && (
        <p className="tw-alert" role="status">{alerts.length === 1 ? tr("1 of your trips needs attention today.", "1 de vos trajets demande votre attention aujourd'hui.") : tr(`${alerts.length} of your trips need attention today.`, `${alerts.length} de vos trajets demandent votre attention aujourd'hui.`)}</p>
      )}
      <ul className="tw-list">
        {trips.map((t, i) => {
          const s = status[i];
          const w = s ? WORD(s.status) : null;
          return (
            <li key={t.from.id + t.to.id} className={w?.cls}>
              <div className="tw-row">
                <strong>{t.from.name} → {t.to.name}</strong>
                <button className="ghost small" aria-label={tr(`Remove ${t.from.name} to ${t.to.name}`, `Retirer ${t.from.name} vers ${t.to.name}`)} onClick={() => remove(i)}>{tr("Remove", "Retirer")}</button>
              </div>
              {!STATIC_DEMO && (
                <p className="tiny tw-subs">{tr("Subscribe:", "S'abonner :")}{" "}
                  <a href={feed(region, t, "rss")}>RSS</a>{" · "}
                  <a href={feed(region, t, "ics").replace(/^https?:/, "webcal:")}>{tr("calendar", "agenda")}</a>{" "}
                  <button className="linkish tiny" onClick={() => navigator.clipboard?.writeText(feed(region, t, "ics")).catch(() => undefined)}>{tr("copy calendar link", "copier le lien d'agenda")}</button>
                </p>
              )}
              {s ? <p className="small"><span className="tw-badge">{w?.label}</span>{s.changed && <span className="tw-changed"> {tr("changed since last check", "a changé depuis la dernière vérification")}</span>} {message(s)}</p>
                 : <p className="muted small">{tr("Checking…", "Vérification…")}</p>}
            </li>
          );
        })}
      </ul>
      {!!status[0]?.observed && (
        <p className="muted tiny">{tr("Lift status read:", "État des ascenseurs lu :")} SNCF {status[0].observed.sncf_lift_status?.slice(0, 16).replace("T", " ") ?? "—"}{status[0].observed.idfm_lift_status ? ` UTC · IDFM ${status[0].observed.idfm_lift_status.slice(0, 16).replace("T", " ")}` : ""} UTC.
          {" "}{tr("Also available from the command line", "Aussi disponible en ligne de commande")} (<code>python -m unlock alerts trips.json</code>){tr(" for a daily scheduled check.", " pour une vérification quotidienne programmée.")}</p>
      )}
    </section>
  );
}
