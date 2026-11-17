import { useEffect, useState } from "react";
import { api } from "../api";

type Row = { lift: string; operator: string; name: string; station: string | null; station_id: string | null; share_out: number;
  observations_out: number; observations: number; spells: number; out_since: string | null; status_changed_at: string | null;
  chronic: boolean; entries_per_day: number | null };
type Report = { sources: Record<string, { observations: number; first: string; last: string; span_days: number }>;
  chronic_rule: { share_out: number; min_days: number }; lifts_out_at_least_once: number; lifts: Row[] };

const day = (s: string | null) => (s ? new Date(s.length > 16 ? s : s + ":00").toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "Europe/Paris" }) : "—");

/** Lifts out most often over the recorded daytime observations (the history grows twice a day). */
export function LiftHistory({ onSelect }: { onSelect: (stationId: string) => void }) {
  const [r, setR] = useState<Report | null>(null);
  const [err, setErr] = useState(false);
  useEffect(() => { api.region.historyLifts().then((x) => setR(x as Report)).catch(() => setErr(true)); }, []);
  if (err) return <p className="small muted">No lift-status history recorded for this region yet.</p>;
  if (!r) return <p className="small muted">Loading the history…</p>;
  const src = Object.entries(r.sources);
  const span = Math.max(0, ...src.map(([, s]) => s.span_days));
  const enough = span >= r.chronic_rule.min_days;
  return (
    <section aria-label="Lift-status history">
      <p className="small">
        {src.map(([op, s]) => `${s.observations} daytime ${op} observation${s.observations > 1 ? "s" : ""} since ${day(s.first)}`).join(" · ")}.{" "}
        {enough ? <>A lift out in ≥ {Math.round(r.chronic_rule.share_out * 100)} % of them is marked <strong>chronic</strong>.</>
          : <>UNLOCK records the status twice a day; lifts are called chronic once {r.chronic_rule.min_days} days are recorded (so far {span.toFixed(1)}).</>}
      </p>
      <ul className="rank hist">
        {r.lifts.slice(0, 25).map((l) => (
          <li key={l.lift}>
            <button onClick={() => l.station_id && onSelect(l.station_id)} disabled={!l.station_id}>
              <span className="gain hist-share">{Math.round(l.share_out * 100)} %</span>
              <span>
                <strong>{l.station || "—"}</strong>{l.chronic && <span className="pill chronic">chronic</span>}<br />
                <span className="small clamp">{l.name}</span>
                <span className="muted tiny">{l.operator} · out in {l.observations_out} of {l.observations} observations
                  {l.out_since ? ` · out at every observation since ${day(l.out_since)}` : ""}
                  {l.status_changed_at ? ` · IDFM status unchanged since ${day(l.status_changed_at)}` : ""}</span>
              </span>
            </button>
          </li>
        ))}
      </ul>
      <p className="muted tiny">{r.lifts_out_at_least_once} lifts of this region were out at least once. Durations are bounded by the observation times; night observations are left out (lifts switched off at the end of service).</p>
    </section>
  );
}
