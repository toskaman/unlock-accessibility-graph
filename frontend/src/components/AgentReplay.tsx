import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { tr } from "../i18n";
import type { AgentSession } from "../types";

const LABEL = (id: string) => ({
  rider: tr("A rider asks, in French", "Un usager demande"),
  shared_rider: tr("Agent 1 writes a report", "Agent 1 signale une panne"),
  shared_maintenance: tr("Agent 2 reads it back", "Agent 2 relit la mémoire"),
  maintenance: tr("A maintenance planner", "Une équipe de maintenance"),
} as Record<string, string>)[id] || id;
const LANG: Record<string, string> = { rider: "fr", shared_rider: "fr", shared_maintenance: "en", maintenance: "en" };
/** The answers are Markdown: keep the bold and the line breaks, nothing else. */
const md = (t: string) => t.trim().split(/\*\*(.+?)\*\*/g).map((x, i) => (i % 2 ? <strong key={i}>{x}</strong> : x));
const args = (o: Record<string, unknown>) => Object.entries(o).map(([k, v]) => `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`).join(", ");

/** Replays real, unedited agent sessions: Claude with UNLOCK's graph as its only tools. */
export function AgentReplay({ onTrip }: { onTrip?: (from: { id: string; name: string }, to: { id: string; name: string }) => void }) {
  const [sessions, setSessions] = useState<AgentSession[]>([]);
  const [cur, setCur] = useState(0);
  const [shown, setShown] = useState<number | null>(null);   // null = everything shown
  const timer = useRef<number | null>(null);
  useEffect(() => { api.agentDemo().then((d) => setSessions(d.sessions)).catch(() => setSessions([])); }, []);
  useEffect(() => () => { if (timer.current) window.clearInterval(timer.current); }, []);
  if (!sessions.length) return null;
  const s = sessions[Math.min(cur, sessions.length - 1)];
  const steps = s.calls.length + 2;        // question, each call, answer
  const visible = (k: number) => shown == null || k < shown;
  const replay = () => {
    if (timer.current) window.clearInterval(timer.current);
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) { setShown(null); return; }
    let k = 1; setShown(1);
    timer.current = window.setInterval(() => {
      k += 1;
      if (k > steps) { if (timer.current) window.clearInterval(timer.current); setShown(null); return; }
      setShown(k);
    }, 1100);
  };
  const pick = (i: number) => { if (timer.current) window.clearInterval(timer.current); setShown(null); setCur(i); };

  return (
    <section className="agentreplay" aria-labelledby="ar-h">
      <h2 id="ar-h">{tr("Ask an AI agent", "Demander à un agent IA")}</h2>
      <p className="muted small">{tr("Real sessions, unedited: Claude with UNLOCK's graph as its only tools. Every fact in the answers comes from a tool call.",
        "Des sessions réelles, non retouchées : Claude, avec le graphe d'UNLOCK pour seuls outils. Chaque fait des réponses vient d'un appel d'outil.")}</p>
      <div className="ar-pick" role="group" aria-label={tr("Sessions", "Sessions")}>
        {sessions.map((x, i) => (
          <button key={x.id} className={i === cur ? "on" : ""} aria-pressed={i === cur} onClick={() => pick(i)}>{LABEL(x.id)}</button>
        ))}
      </div>
      <ol className="ar-steps" aria-live="polite">
        {visible(0) && <li className="ar-q" lang={LANG[s.id]}><span className="ar-who">{tr("Question", "Question")}</span>{md(s.prompt)}</li>}
        {s.calls.map((c, i) => visible(i + 1) && (
          <li key={i} className="ar-call">
            <span className="ar-who">{tr("Tool call", "Appel d'outil")} {i + 1}</span>
            <code>{c.name}({args(c.input)})</code>
            <details><summary>{tr("What the graph returned", "Ce que le graphe a renvoyé")}</summary>
              <pre>{c.result}{c.truncated ? " …" : ""}</pre></details>
          </li>
        ))}
        {visible(steps - 1) && <li className="ar-a" lang={LANG[s.id]}><span className="ar-who">{tr("Answer", "Réponse")}</span>{md(s.answer)}</li>}
      </ol>
      <div className="report-actions">
        <button className="ghost small" onClick={replay}>{tr("▶ Replay step by step", "▶ Rejouer pas à pas")}</button>
        {s.id === "rider" && onTrip && (
          <button className="ghost small" onClick={() => onTrip({ id: "73798", name: "Rosa Parks" }, { id: "478505", name: "Juvisy" })}>
            {tr("Check this trip on the map", "Vérifier ce trajet sur la carte")}</button>
        )}
      </div>
      <p className="muted tiny">{s.model ? `${s.model} · ` : ""}{s.seconds ? `${Math.round(s.seconds)} s · ` : ""}{tr("transcript: docs/AGENT_DEMO.md", "transcription : docs/AGENT_DEMO.md")}</p>
    </section>
  );
}
