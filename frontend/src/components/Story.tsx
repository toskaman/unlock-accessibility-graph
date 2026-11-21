import { useState } from "react";
import { tr } from "../i18n";

const KEY = "unlock.story.done";
const seen = () => { try { return localStorage.getItem(KEY) === "1"; } catch { return true; } };

/** First visit only: the story in three cards, then straight into the tool. */
export function Story({ onDone }: { onDone: () => void }) {
  const [open, setOpen] = useState(() => !seen());
  if (!open) return null;
  const close = () => { setOpen(false); try { localStorage.setItem(KEY, "1"); } catch { /* ignore */ } onDone(); };
  const cards = [
    { n: "1", t: tr("One lift breaks", "Un ascenseur tombe en panne"), b: tr("For a wheelchair user, one broken lift can cut off a whole station — and every trip through it.", "En fauteuil, un seul ascenseur en panne peut couper toute une gare — et tous les trajets qui y passent.") },
    { n: "2", t: tr("The official feed doesn't say", "Le flux officiel ne le dit pas"), b: tr("The regional outage feed is weeks out of date. The operators' own data contradict it.", "Le flux régional des pannes a des semaines de retard. Les données des opérateurs eux-mêmes le contredisent.") },
    { n: "3", t: tr("UNLOCK finds the repair that matters", "UNLOCK trouve la réparation qui compte"), b: tr("Every station, platform and lift in one Relate graph: which trips work today, and which single repair gives back the most.", "Chaque gare, quai et ascenseur dans un seul graphe Relate : quels trajets marchent aujourd'hui, et quelle réparation en rend le plus.") },
  ];
  return (
    <section className="story" aria-labelledby="story-h">
      <h2 id="story-h">{tr("Can a wheelchair user get there today?", "Peut-on y aller en fauteuil aujourd'hui ?")}</h2>
      <ol>{cards.map((c, i) => <li key={c.n} style={{ animationDelay: `${0.15 + i * 0.2}s` }}><b>{c.n}</b><h3>{c.t}</h3><p>{c.b}</p></li>)}</ol>
      <button className="primary" onClick={close} autoFocus>{tr("Show me the map", "Voir la carte")}</button>
    </section>
  );
}
