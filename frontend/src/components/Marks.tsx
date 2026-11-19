/** The visual vocabulary of UNLOCK: a lift glyph, and the three station marks used on the map, the legend and the
 *  lists — shape first, colour second, so the states read without colour too. */
export type MarkKind = "open" | "ok" | "doubt" | "cut" | "dim";

export function LiftGlyph({ size = 18, title }: { size?: number; title?: string }) {
  return (
    <svg className="liftglyph" width={size} height={size} viewBox="0 0 20 20" role={title ? "img" : undefined} aria-hidden={title ? undefined : true}
         aria-label={title} focusable="false">
      <rect x="2" y="2" width="16" height="16" rx="2.5" fill="none" stroke="currentColor" strokeWidth="2" />
      <path d="M6.2 8.6 8.6 5.4 11 8.6Z M9 11.4 11.4 14.6 13.8 11.4Z" fill="currentColor" />
    </svg>
  );
}

export function StateMark({ kind, size = 14 }: { kind: MarkKind; size?: number }) {
  const c = { open: "var(--ink)", ok: "var(--ok)", doubt: "var(--doubt-mark)", cut: "var(--ko)", dim: "var(--map-dim)" }[kind];
  return (
    <svg className="statemark" width={size} height={size} viewBox="0 0 14 14" aria-hidden="true" focusable="false">
      {kind === "open" && <circle cx="7" cy="7" r="4" fill={c} />}
      {kind === "ok" && <circle cx="7" cy="7" r="5" fill={c} />}
      {kind === "doubt" && <circle cx="7" cy="7" r="4.6" fill="var(--panel)" stroke={c} strokeWidth="2.4" />}
      {kind === "cut" && <path d="M3 3 11 11 M11 3 3 11" stroke={c} strokeWidth="3" strokeLinecap="round" />}
      {kind === "dim" && <circle cx="7" cy="7" r="2.2" fill={c} />}
    </svg>
  );
}
