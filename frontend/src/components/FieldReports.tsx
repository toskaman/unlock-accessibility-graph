import { useEffect, useState } from "react";
import { api, STATIC_DEMO } from "../api";
import { isFr, tr } from "../i18n";
import type { FieldReport } from "../types";

type LiftRow = { id: string; operator: string; status: string; direction: string | null; name?: string | null };
const liftLabel = (l: LiftRow) => l.name || l.direction || l.id;

const VERDICT = (v: FieldReport["verdict"]) => ({
  CONFIRMS: tr("confirms the official status", "confirme l'état officiel"),
  CONTRADICTS: tr("contradicts the official status", "contredit l'état officiel"),
  NEW_INFO: tr("official status unknown", "état officiel inconnu"),
})[v];
const SOURCE = (s: string) => ({ rider: tr("rider", "usager"), staff: tr("staff", "personnel"), agent: tr("AI agent", "agent IA") } as Record<string, string>)[s] || s;
const ago = (h: number) => (h < 1 ? tr(`${Math.max(1, Math.round(h * 60))} min ago`, `il y a ${Math.max(1, Math.round(h * 60))} min`) : tr(`${Math.round(h)} h ago`, `il y a ${Math.round(h)} h`));

function saved(lift: string, r: FieldReport): string {
  const off = r.official_status === "AVAILABLE" ? tr("working", "en service") : tr("out of service", "hors service");
  if (isFr()) return r.verdict === "NEW_INFO" ? `Signalement enregistré pour « ${lift} ». L'état officiel est inconnu : c'est une information nouvelle.`
    : `Signalement enregistré pour « ${lift} » : il ${r.verdict === "CONFIRMS" ? "confirme" : "contredit"} l'état officiel (${off}).`;
  return r.verdict === "NEW_INFO" ? `Report saved for “${lift}”. The official status is unknown, so this is new information.`
    : `Report saved for “${lift}”: it ${r.verdict === "CONFIRMS" ? "confirms" : "contradicts"} the official status (${off}).`;
}

/** Field reports at one station: read back from the shared graph (installed app) or this browser (demo),
 *  each set against the official status. A report never changes the official status or any count. */
export function FieldReports({ stationId, lifts, canReport }: { stationId: string; lifts: LiftRow[]; canReport: boolean }) {
  const [rows, setRows] = useState<FieldReport[] | null>(null);
  const [lift, setLift] = useState(lifts[0]?.id || "");
  const [status, setStatus] = useState<"OUT" | "WORKING">("OUT");
  const [note, setNote] = useState("");
  const [sent, setSent] = useState<FieldReport | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const load = () => api.region.reports(stationId).then((r) => setRows(r.reports)).catch(() => setRows([]));
  useEffect(() => { setLift(lifts[0]?.id || ""); setSent(null); setErr(null); load(); }, [stationId]); // eslint-disable-line react-hooks/exhaustive-deps

  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    try {
      const r = await api.region.addReport({ lift, status, note, source: "rider" });
      setSent(r); setNote(""); load();
    } catch (x) { setErr(String((x as Error)?.message || x)); }
  };
  const name = (id: string) => { const l = lifts.find((x) => x.id === id); return l ? liftLabel(l) : id; };

  return (
    <section className="freports" aria-labelledby={`fr-${stationId}`}>
      <h4 id={`fr-${stationId}`}>{tr("Field reports", "Signalements terrain")}</h4>
      {rows && rows.length > 0 ? (
        <ul className="olist">
          {rows.map((r) => (
            <li key={r.id}>
              <p><span className={`pst s-${r.status === "OUT" ? "CLOSED" : "OPEN"}`}>{r.status === "OUT" ? tr("seen out of service", "vu hors service") : tr("seen working", "vu en service")}</span>{" "}
                {r.label}</p>
              <p className="tiny"><span className={`fr-verdict fr-${r.verdict}`}>{VERDICT(r.verdict)}</span>
                {" · "}{SOURCE(r.source)}{r.reporter ? ` (${r.reporter})` : ""} · {ago(r.age_hours)}{r.recent ? "" : tr(" · old", " · ancien")}</p>
              {r.other_official && !r.other_official.agrees && (
                <p className="tiny muted">{tr(`The two official sources disagree here: ${r.official_source} says ${r.official_status.toLowerCase()}, IDFM's dataset says ${r.other_official.status.toLowerCase()}.`,
                  `Les deux sources officielles ne sont pas d'accord ici : l'état horaire SNCF dit « ${r.official_status === "AVAILABLE" ? "en service" : r.official_status === "UNAVAILABLE" ? "hors service" : "inconnu"} », les données IDFM « ${r.other_official.status === "AVAILABLE" ? "en service" : r.other_official.status === "UNAVAILABLE" ? "hors service" : "inconnu"} ».`)}</p>
              )}
              {r.note && <p className="tiny muted">« {r.note} »</p>}
            </li>
          ))}
        </ul>
      ) : <p className="muted tiny">{rows ? tr("No report in the last 24 hours.", "Aucun signalement depuis 24 heures.") : tr("Loading…", "Chargement…")}</p>}
      <p className="muted tiny">{tr("Reports come from riders, staff and AI agents. They never change the official status or any count: UNLOCK only compares them with it.",
        "Les signalements viennent d'usagers, du personnel et d'agents IA. Ils ne changent jamais l'état officiel ni aucun chiffre : UNLOCK les compare seulement avec lui.")}</p>
      {canReport && lifts.length > 0 && (
        <details className="fr-form">
          <summary>{tr("Report what you see", "Signaler ce que vous voyez")}</summary>
          <form onSubmit={send}>
            <label>{tr("Lift", "Ascenseur")}
              <select value={lift} onChange={(e) => setLift(e.target.value)}>
                {lifts.map((l) => <option key={l.id} value={l.id}>{`${liftLabel(l).slice(0, 80)} (${l.status === "AVAILABLE" ? tr("working", "en service") : l.status === "UNAVAILABLE" ? tr("out of service", "hors service") : tr("unknown", "inconnu")})`}</option>)}
              </select>
            </label>
            <fieldset>
              <legend>{tr("What did you see?", "Qu'avez-vous constaté ?")}</legend>
              <label><input type="radio" name={`st-${stationId}`} checked={status === "OUT"} onChange={() => setStatus("OUT")} /> {tr("Out of service", "Hors service")}</label>
              <label><input type="radio" name={`st-${stationId}`} checked={status === "WORKING"} onChange={() => setStatus("WORKING")} /> {tr("Working", "En service")}</label>
            </fieldset>
            <label>{tr("Note (optional)", "Précision (facultatif)")}
              <input value={note} maxLength={280} onChange={(e) => setNote(e.target.value)} placeholder={tr("e.g. seen at 8:10, door stuck", "ex. vu à 8 h 10, porte bloquée")} />
            </label>
            <button className="primary small" type="submit" disabled={!lift}>{tr("Send the report", "Envoyer le signalement")}</button>
            {STATIC_DEMO && <p className="muted tiny">{tr("In this demo, reports stay in your browser. In the installed app they go into the shared graph, where every agent reads them.", "Dans cette démo, les signalements restent dans votre navigateur. Dans l'application installée, ils vont dans le graphe partagé, où tous les agents les lisent.")}</p>}
          </form>
        </details>
      )}
      <p role="status" className="tiny">{sent ? saved(name(sent.lift), sent) : err ? tr(`Could not save the report: ${err}`, `Le signalement n'a pas pu être enregistré : ${err}`) : ""}</p>
    </section>
  );
}
