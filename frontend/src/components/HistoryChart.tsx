import { useEffect, useState } from "react";
import { api } from "../api";

type Obs = { sncf_observed_at: string | null; idfm_observed_at: string | null; night: boolean; published: number; confirmed: number; possible: number };

/** Confirmed step-free journeys at each recorded lift-status observation (shown once there are two). */
export function HistoryChart() {
  const [obs, setObs] = useState<Obs[]>([]);
  useEffect(() => { api.region.history().then((h) => setObs(h.observations as Obs[])).catch(() => setObs([])); }, []);
  if (obs.length < 2) return null;
  const W = 520, H = 120, P = 26;
  const t = (o: Obs) => new Date(([o.sncf_observed_at, o.idfm_observed_at].filter(Boolean) as string[]).sort().slice(-1)[0]).getTime();
  const xs = obs.map(t), x0 = Math.min(...xs), x1 = Math.max(...xs) || x0 + 1;
  const top = Math.max(...obs.map((o) => o.published)), lo = Math.min(...obs.map((o) => o.confirmed));
  const y0 = Math.max(0, lo - (top - lo) * 0.15);
  const X = (v: number) => P + ((v - x0) / (x1 - x0 || 1)) * (W - 2 * P), Y = (v: number) => H - P / 2 - ((v - y0) / (top - y0 || 1)) * (H - P);
  const day = obs.filter((o) => !o.night);
  const line = day.map((o) => `${X(t(o))},${Y(o.confirmed)}`).join(" ");
  return (
    <figure className="histchart">
      <figcaption className="small">Confirmed journeys at each recorded observation ({obs.length}; hollow = night snapshot)</figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Confirmed step-free journeys over ${obs.length} observations, from ${obs[0].confirmed.toLocaleString("en-GB")} to ${obs[obs.length - 1].confirmed.toLocaleString("en-GB")}`}>
        <line x1={P} x2={W - P} y1={Y(top)} y2={Y(top)} className="hc-pub" />
        <text x={P} y={Y(top) - 4} className="hc-lbl">published {top.toLocaleString("en-GB")}</text>
        {day.length > 1 && <polyline points={line} className="hc-line" />}
        {obs.map((o, i) => <circle key={i} cx={X(t(o))} cy={Y(o.confirmed)} r={3.5} className={o.night ? "hc-night" : "hc-dot"}><title>{new Date(t(o)).toLocaleString("en-GB", { timeZone: "Europe/Paris" })}: {o.confirmed.toLocaleString("en-GB")}</title></circle>)}
      </svg>
    </figure>
  );
}
