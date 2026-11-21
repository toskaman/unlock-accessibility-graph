import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { fmtDate, isFr, num, tr } from "../i18n";

type Frame = { t: string; night: boolean; confirmed: number; published: number; stations: Record<string, string> };
const when = (t: string) => fmtDate(new Date(t), { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Paris" });

/** Confirmed journeys at each recorded observation, and a time-lapse that replays the map frame by frame.
 *  Shown once two observations exist; the history grows twice a day. */
export function HistoryChart({ onFrame, playSignal = 0 }: { onFrame?: (states: Record<string, string> | null) => void; playSignal?: number }) {
  const [frames, setFrames] = useState<Frame[]>([]);
  const [i, setI] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const [dayOnly, setDayOnly] = useState(true);
  const timer = useRef<number | null>(null);
  const playRef = useRef<(() => void) | null>(null);
  useEffect(() => { api.region.timelapse().then((h) => setFrames(h.frames)).catch(() => setFrames([])); }, []);
  useEffect(() => () => { if (timer.current) window.clearInterval(timer.current); onFrame?.(null); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const shown = frames.filter((f) => !dayOnly || !f.night);
  useEffect(() => { onFrame?.(i == null || !shown[i] ? null : shown[i].stations); }, [i, dayOnly, frames]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (playSignal && frames.length >= 2 && !playing) playRef.current?.(); }, [playSignal]); // eslint-disable-line
  if (frames.length < 2) return null;

  const play = () => {
    if (playing) { if (timer.current) window.clearInterval(timer.current); setPlaying(false); return; }
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    setPlaying(true);
    let k = 0;
    setI(0);
    timer.current = window.setInterval(() => {
      k += 1;
      if (k >= shown.length) { if (timer.current) window.clearInterval(timer.current); setPlaying(false); return; }
      setI(k);
    }, reduce ? 2500 : 900);
  };
  playRef.current = play;
  const stop = () => { if (timer.current) window.clearInterval(timer.current); setPlaying(false); setI(null); };

  const W = 520, H = 110, P = 26;
  const pts = shown.length ? shown : frames;
  const xs = pts.map((f) => new Date(f.t).getTime()), x0 = Math.min(...xs), x1 = Math.max(...xs);
  const top = Math.max(...pts.map((f) => f.published)), lo = Math.min(...pts.map((f) => f.confirmed));
  const y0 = Math.max(0, lo - (top - lo) * 0.15 - 1);
  const X = (v: number) => P + ((v - x0) / (x1 - x0 || 1)) * (W - 2 * P);
  const Y = (v: number) => H - P / 2 - ((v - y0) / (top - y0 || 1)) * (H - P);
  const cur = i == null ? null : shown[i];
  return (
    <figure className="histchart">
      <figcaption className="small">
        {isFr() ? `Trajets confirmés à chaque relevé enregistré (${shown.length}${dayOnly ? " de jour" : ""} ; cercle vide = nuit).`
          : `Confirmed journeys at each recorded observation (${shown.length}${dayOnly ? " daytime" : ""}; hollow = night).`}{" "}
        <button className="ghost small" onClick={play} disabled={shown.length < 2}>{playing ? tr("Pause", "Pause") : tr("▶ Replay on the map", "▶ Rejouer sur la carte")}</button>{" "}
        {i != null && <button className="ghost small" onClick={stop}>{tr("Back to now", "Revenir à maintenant")}</button>}{" "}
        <label className="tiny"><input type="checkbox" checked={!dayOnly} onChange={(e) => { setDayOnly(!e.target.checked); setI(null); }} /> {tr("include night snapshots", "inclure les relevés de nuit")}</label>
      </figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={tr(`Confirmed step-free journeys over ${pts.length} observations, from ${num(pts[0].confirmed)} to ${num(pts[pts.length - 1].confirmed)}`, `Trajets sans marche confirmés sur ${pts.length} relevés, de ${num(pts[0].confirmed)} à ${num(pts[pts.length - 1].confirmed)}`)}>
        <line x1={P} x2={W - P} y1={Y(top)} y2={Y(top)} className="hc-pub" />
        <text x={P} y={Y(top) - 4} className="hc-lbl">{tr("published", "publiés")} {num(top)}</text>
        {pts.length > 1 && <polyline points={pts.map((f) => `${X(new Date(f.t).getTime())},${Y(f.confirmed)}`).join(" ")} className="hc-line" />}
        {pts.map((f) => (
          <circle key={f.t} cx={X(new Date(f.t).getTime())} cy={Y(f.confirmed)} r={cur === f ? 6 : 3.5} className={f.night ? "hc-night" : "hc-dot"}
                  onClick={() => setI(shown.indexOf(f) >= 0 ? shown.indexOf(f) : null)}>
            <title>{when(f.t)} : {num(f.confirmed)}</title>
          </circle>
        ))}
      </svg>
      {cur && <p className="small hc-now" aria-live="polite">{tr("Map at", "Carte au")} <strong>{when(cur.t)}</strong>{cur.night ? tr(" (night)", " (nuit)") : ""}{tr(": ", " : ")}{tr(`${num(cur.confirmed)} confirmed journeys, ${Object.keys(cur.stations).length} stations not fully open.`, `${num(cur.confirmed)} trajets confirmés, ${Object.keys(cur.stations).length} gares pas entièrement ouvertes.`)}</p>}
    </figure>
  );
}
