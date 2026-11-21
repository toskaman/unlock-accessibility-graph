import type { Leg } from "../types";
import { tr } from "../i18n";

const WORD: Record<string, [string, string]> = { OPEN: ["open", "ouvert"], DOUBT: ["lift listed out", "ascenseur signalé en panne"], CLOSED: ["cut off", "coupé"] };
const word = (s: string) => tr(...(WORD[s] || [s.toLowerCase(), s.toLowerCase()]));

/** The trip as the graph sees it: platform → ride → platform, each platform marked by the lift status that serves it. */
export function PathChain({ legs }: { legs: Leg[] }) {
  return (
    <figure className="pathchain" aria-label={tr("The path in the graph", "Le chemin dans le graphe")}>
      <figcaption className="tiny muted">{tr("The path in the graph: platform → ride → platform", "Le chemin dans le graphe : quai → trajet → quai")}</figcaption>
      <ol>
        {legs.map((l, i) => (
          <li key={i} style={{ animationDelay: `${i * 0.18}s` }}>
            <span className={`pc-node s-${l.board_state}`}><i />{l.from_name}<em>{word(l.board_state)}</em></span>
            <span className="pc-ride" style={{ background: `#${l.color || "5d6f91"}`, color: `#${l.text_color || "ffffff"}` }}>{l.line_name}</span>
            {i === legs.length - 1 && <span className={`pc-node s-${l.alight_state}`}><i />{l.to_name}<em>{word(l.alight_state)}</em></span>}
          </li>
        ))}
      </ol>
    </figure>
  );
}
