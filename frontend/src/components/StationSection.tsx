import { useMemo } from "react";
import type { LiftState, StationGraph } from "../types";

type Props = {
  graph: StationGraph;
  selectedLift: string | null;
  simulated: Set<string>;
  candidate: string | null;
  highlight: string[] | null;
  lostSpaces: Set<string>;
  onSelectLift: (id: string) => void;
};

const ROW = { top: 84, mid: 206, bot: 330 };
const H = 392;
const MIN_GAP = 128;

const TOP_ROLES = new Set(["EXIT", "UNRESOLVED", "PRIVATE"]);
const BOT_ROLES = new Set(["PLATFORM", "UNRESOLVED_PLATFORM"]);

export const STATE_LABEL: Record<LiftState, string> = {
  AVAILABLE: "Working", UNAVAILABLE: "Out of service", UNKNOWN: "Status unknown",
};

function natural(a: string, b: string) {
  return a.localeCompare(b, "fr", { numeric: true, sensitivity: "base" });
}

function short(s: string, n = 24) {
  const t = s.charAt(0).toUpperCase() + s.slice(1);
  return t.length > n ? t.slice(0, n - 1) + "…" : t;
}

export function layoutStation(g: StationGraph) {
  const spaceById = new Map(g.spaces.map((s) => [s.id, s]));
  const liftEnds = new Map<string, string[]>();
  g.serves.forEach((e) => {
    const arr = liftEnds.get(e.lift) || [];
    arr.push(e.space);
    liftEnds.set(e.lift, arr);
  });
  const neighbours = new Map<string, Set<string>>();
  liftEnds.forEach((ends) => {
    const real = ends.filter((s) => spaceById.get(s)?.role !== "UNSPECIFIED");
    real.forEach((a) => real.forEach((b) => {
      if (a !== b) {
        if (!neighbours.has(a)) neighbours.set(a, new Set());
        neighbours.get(a)!.add(b);
      }
    }));
  });

  const bottom = g.spaces.filter((s) => BOT_ROLES.has(s.role)).sort((a, b) => natural(a.name, b.name));
  const middle = g.spaces.filter((s) => s.role === "CONNECTOR");
  const top = g.spaces.filter((s) => TOP_ROLES.has(s.role));
  const width = Math.max(960, 260 + Math.max(bottom.length, middle.length, top.length) * MIN_GAP);
  const pos = new Map<string, { x: number; y: number }>();
  const step = bottom.length > 1 ? (width - 300) / (bottom.length - 1) : 0;
  bottom.forEach((s, i) => pos.set(s.id, { x: bottom.length > 1 ? 230 + i * step : width / 2, y: ROW.bot }));

  const placeRow = (row: typeof middle, y: number) => {
    const xs = row.map((s, i) => {
      const ns = [...(neighbours.get(s.id) || [])].map((n) => pos.get(n)).filter(Boolean) as { x: number }[];
      const x = ns.length ? ns.reduce((t, p) => t + p.x, 0) / ns.length : 230 + (i * (width - 300)) / Math.max(1, row.length - 1);
      return { s, x };
    }).sort((a, b) => a.x - b.x || natural(a.s.name, b.s.name));
    for (let i = 1; i < xs.length; i++) xs[i].x = Math.max(xs[i].x, xs[i - 1].x + MIN_GAP);
    const overflow = xs.length ? xs[xs.length - 1].x - (width - 80) : 0;
    if (overflow > 0) xs.forEach((p) => (p.x -= overflow));
    for (let i = xs.length - 2; i >= 0; i--) xs[i].x = Math.min(xs[i].x, xs[i + 1].x - MIN_GAP);
    const shift = xs.length ? Math.max(0, 230 - xs[0].x) : 0;
    xs.forEach((p) => pos.set(p.s.id, { x: p.x + shift, y }));
  };
  placeRow(middle, ROW.mid);
  placeRow(top, ROW.top);

  const liftPos = new Map<string, { x: number; y: number; ends: { x: number; y: number }[]; open: boolean }>();
  const used = new Map<string, number>();
  g.lifts.forEach((l) => {
    const ends = (liftEnds.get(l.id) || []).filter((s) => spaceById.get(s)?.role !== "UNSPECIFIED")
      .map((s) => pos.get(s)).filter(Boolean) as { x: number; y: number }[];
    const open = (liftEnds.get(l.id) || []).some((s) => spaceById.get(s)?.role === "UNSPECIFIED");
    let x = width / 2, y = ROW.mid;
    if (ends.length >= 2) {
      x = ends.reduce((t, p) => t + p.x, 0) / ends.length;
      const ys = ends.map((p) => p.y);
      y = Math.max(...ys) === Math.min(...ys) ? ys[0] - 52 : (Math.max(...ys) + Math.min(...ys)) / 2;
    } else if (ends.length === 1) {
      x = ends[0].x; y = ends[0].y - 62;
    }
    const key = `${Math.round(x / 20)}:${Math.round(y / 20)}`;
    const k = used.get(key) || 0;
    used.set(key, k + 1);
    liftPos.set(l.id, { x: x + (k % 2 ? 1 : -1) * Math.ceil(k / 2) * 30, y, ends, open });
  });
  return { width, pos, liftPos, liftEnds, spaceById };
}

export function StationSection({ graph, selectedLift, simulated, candidate, highlight, lostSpaces, onSelectLift }: Props) {
  const L = useMemo(() => layoutStation(graph), [graph]);
  const hl = new Set(highlight || []);
  const hasPlatforms = graph.spaces.some((s) => BOT_ROLES.has(s.role));

  if (!graph.lifts.length) {
    return <p className="empty">The source lists no lifts for this station, so there is nothing to simulate here.</p>;
  }

  return (
    <div className="section-scroll" role="group" aria-label={`Cross-section of ${graph.station.name}: spaces and the lifts that connect them`}>
      <svg viewBox={`0 0 ${L.width} ${H}`} className="section-svg" style={{ width: "100%", minWidth: L.width * 0.92, maxWidth: L.width * 1.25, height: "auto" }}>
        <defs>
          <pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="6" height="6" fill="var(--unverified-bg)" />
            <line x1="0" y1="0" x2="0" y2="6" stroke="var(--unverified)" strokeWidth="2" />
          </pattern>
        </defs>
        <g className="rows" aria-hidden="true">
          <text x={12} y={ROW.top + 4}>Halls &amp; exits</text>
          <text x={12} y={ROW.mid - 4}>Underpasses &amp;<tspan x={12} dy={16}>footbridges</tspan></text>
          {hasPlatforms && <text x={12} y={ROW.bot + 4}>Platforms</text>}
          <line x1={0} x2={L.width} y1={ROW.bot + 34} y2={ROW.bot + 34} className="trackbed" />
        </g>

        {graph.lifts.map((l) => {
          const p = L.liftPos.get(l.id)!;
          const onRoute = hl.has(l.id);
          return (
            <g key={`e-${l.id}`} className={`edges state-${l.state}${onRoute ? " on-route" : ""}`}>
              {p.ends.map((e, i) => <line key={i} x1={p.x} y1={p.y} x2={e.x} y2={e.y} />)}
              {p.open && <line className="open-end" x1={p.x} y1={p.y} x2={p.x + 34} y2={p.y - 30} />}
            </g>
          );
        })}

        {graph.spaces.filter((s) => s.role !== "UNSPECIFIED").map((s) => {
          const p = L.pos.get(s.id);
          if (!p) return null;
          const lost = lostSpaces.has(s.id);
          const on = hl.has(s.id);
          if (BOT_ROLES.has(s.role)) {
            const w = 104;
            return (
              <g key={s.id} className={`platform${lost ? " lost" : ""}${on ? " on-route" : ""}${s.role === "UNRESOLVED_PLATFORM" ? " text-only" : ""}`}>
                <rect x={p.x - w / 2} y={p.y - 9} width={w} height={18} rx={3}
                      fill={s.step_free === "INACCESSIBLE" ? "url(#hatch)" : undefined} />
                <text x={p.x} y={p.y + 30} textAnchor="middle">{short(s.quay_name || s.name, 18)}</text>
                <title>{`${s.quay_name || s.name}${s.step_free ? ` — source step-free assessment: ${s.step_free.toLowerCase()}` : " — no quay match in source"}`}</title>
              </g>
            );
          }
          const w = Math.min(150, 26 + short(s.name).length * 7.2);
          return (
            <g key={s.id} className={`space role-${s.role}${lost ? " lost" : ""}${on ? " on-route" : ""}`}>
              <rect x={p.x - w / 2} y={p.y - 15} width={w} height={30} rx={15} />
              <text x={p.x} y={p.y + 5} textAnchor="middle">{short(s.name)}</text>
              <title>{`${s.name} (${s.role.toLowerCase().replace("_", " ")})`}</title>
            </g>
          );
        })}

        {graph.lifts.map((l) => {
          const p = L.liftPos.get(l.id)!;
          const sim = simulated.has(l.id);
          const cand = candidate === l.id;
          const sel = selectedLift === l.id;
          return (
            <g key={l.id} className={`lift state-${l.state}${sim ? " simulated" : ""}${cand ? " candidate" : ""}${sel ? " selected" : ""}`}
               transform={`translate(${p.x},${p.y})`} role="button" tabIndex={0}
               aria-pressed={sel}
               aria-label={`Lift ${l.name || l.id}: ${STATE_LABEL[l.state]}${sim ? ", simulated outage" : ""}${cand ? ", proposed repair" : ""}. ${l.description || ""}`}
               onClick={() => onSelectLift(l.id)}
               onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelectLift(l.id); } }}>
              {(sim || cand || sel) && <rect className="ring" x={-21} y={-21} width={42} height={42} rx={9} />}
              <rect className="cab" x={-14} y={-14} width={28} height={28} rx={5} />
              {l.state === "UNAVAILABLE"
                ? <path className="glyph" d="M-6 -6 L6 6 M6 -6 L-6 6" />
                : l.state === "UNKNOWN"
                  ? <text className="glyph-q" y={5} textAnchor="middle">?</text>
                  : <path className="glyph" d="M-5 -2 L0 -8 L5 -2 M-5 2 L0 8 L5 2" />}
              <title>{`${l.name || l.id} — ${STATE_LABEL[l.state]}${l.overridden ? " (simulated)" : ""}\n${l.description || "No location text"}`}</title>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
