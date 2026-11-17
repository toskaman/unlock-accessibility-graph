import { useEffect, useState } from "react";
import { api } from "../api";
import { fmtDay, isFr, tr } from "../i18n";

type Row = { lift: string; operator: string; name: string; station: string | null; station_id: string | null; share_out: number;
  observations_out: number; observations: number; spells: number; out_since: string | null; status_changed_at: string | null;
  chronic: boolean; entries_per_day: number | null };
type Report = { sources: Record<string, { observations: number; first: string; last: string; span_days: number }>;
  chronic_rule: { share_out: number; min_days: number }; lifts_out_at_least_once: number; lifts: Row[] };

const day = (s: string | null) => (s ? fmtDay(new Date(s.length > 16 ? s : s + ":00"), { day: "numeric", month: "short", timeZone: "Europe/Paris" }) : "—");

/** Lifts out most often over the recorded daytime observations (the history grows twice a day). */
export function LiftHistory({ onSelect }: { onSelect: (stationId: string) => void }) {
  const [r, setR] = useState<Report | null>(null);
  const [err, setErr] = useState(false);
  useEffect(() => { api.region.historyLifts().then((x) => setR(x as Report)).catch(() => setErr(true)); }, []);
  if (err) return <p className="small muted">{tr("No lift-status history recorded for this region yet.", "Aucun historique de l'état des ascenseurs n'est encore enregistré pour cette région.")}</p>;
  if (!r) return <p className="small muted">{tr("Loading the history…", "Chargement de l'historique…")}</p>;
  const src = Object.entries(r.sources);
  const span = Math.max(0, ...src.map(([, s]) => s.span_days));
  const enough = span >= r.chronic_rule.min_days;
  return (
    <section aria-label={tr("Lift-status history", "Historique de l'état des ascenseurs")}>
      <p className="small">
        {src.map(([op, s]) => isFr() ? `${s.observations} ${s.observations > 1 ? "relevés" : "relevé"} ${op} de jour depuis le ${day(s.first)}` : `${s.observations} daytime ${op} observation${s.observations > 1 ? "s" : ""} since ${day(s.first)}`).join(" · ").replace(/\.$/, "")}.{" "}
        {enough ? (isFr() ? <>Un ascenseur en panne dans au moins {Math.round(r.chronic_rule.share_out * 100)} % d'entre eux est marqué <strong>chronique</strong>.</>
            : <>A lift out in ≥ {Math.round(r.chronic_rule.share_out * 100)} % of them is marked <strong>chronic</strong>.</>)
          : tr(`UNLOCK records the status twice a day; lifts are called chronic once ${r.chronic_rule.min_days} days are recorded (so far ${span.toFixed(1)}).`,
               `UNLOCK relève l'état deux fois par jour ; un ascenseur sera dit chronique une fois ${r.chronic_rule.min_days} jours enregistrés (pour l'instant ${span.toLocaleString("fr-FR", { maximumFractionDigits: 1 })}).`)}
      </p>
      <ul className="rank hist">
        {r.lifts.slice(0, 25).map((l) => (
          <li key={l.lift}>
            <button onClick={() => l.station_id && onSelect(l.station_id)} disabled={!l.station_id}>
              <span className="gain hist-share">{Math.round(l.share_out * 100)} %</span>
              <span>
                <strong>{l.station || "—"}</strong>{l.chronic && <span className="pill chronic">{tr("chronic", "chronique")}</span>}<br />
                <span className="small clamp">{l.name}</span>
                <span className="muted tiny">{l.operator} · {tr(`out in ${l.observations_out} of ${l.observations} observations`, `en panne à ${l.observations_out} ${l.observations_out > 1 ? "relevés" : "relevé"} sur ${l.observations}`)}
                  {l.out_since ? tr(` · out at every observation since ${day(l.out_since)}`, ` · en panne à chaque relevé depuis le ${day(l.out_since)}`) : ""}
                  {l.status_changed_at ? tr(` · IDFM status unchanged since ${day(l.status_changed_at)}`, ` · état IDFM inchangé depuis le ${day(l.status_changed_at)}`) : ""}</span>
              </span>
            </button>
          </li>
        ))}
      </ul>
      <p className="muted tiny">{tr(`${r.lifts_out_at_least_once} lifts of this region were out at least once. Durations are bounded by the observation times; night observations are left out (lifts switched off at the end of service).`,
        `${r.lifts_out_at_least_once} ascenseurs de cette région ont été en panne au moins une fois. Les durées sont bornées par les heures de relevé ; les relevés de nuit sont écartés (ascenseurs éteints en fin de service).`)}</p>
    </section>
  );
}
