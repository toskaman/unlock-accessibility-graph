import { useState } from "react";
import { isFr } from "../i18n";

const KEY = "unlock.intro.dismissed";
const seen = () => { try { return localStorage.getItem(KEY) === "1"; } catch { return false; } };

/** Three lines that say what the page is, for a first-time visitor. */
export function Intro() {
  const [open, setOpen] = useState(() => !seen());
  if (!open) return null;
  const close = () => { setOpen(false); try { localStorage.setItem(KEY, "1"); } catch { /* ignore */ } };
  return (
    <section className="intro" aria-labelledby="intro-h">
      {isFr() ? <>
      <h2 id="intro-h">Peut-on y aller en fauteuil aujourd'hui ?</h2>
      <p>Chaque point est une gare. Le grand nombre compte les trajets de gare à gare faisables <strong>sans une seule marche aujourd'hui</strong>, selon les ascenseurs qui fonctionnent vraiment ; les points rouges et orange sont des gares qu'un ascenseur en panne coupe du réseau.</p>
      <p>Vérifiez un trajet, cliquez sur une gare pour voir où l'on peut aller depuis elle, ou ouvrez <em>Réparations utiles</em> pour voir quelle réparation rend le plus de trajets.</p>
      <button className="ghost small" onClick={close}>Compris</button>
      </> : <>
      <h2 id="intro-h">Can a wheelchair user get there today?</h2>
      <p>Each dot is a station. The big number counts the station-to-station trips that can be made <strong>without a single step today</strong>, given which lifts actually work — red and amber dots are stations a broken lift cuts off.</p>
      <p>Check a trip, click a station to see where you can go from it, or open <em>Repairs that matter</em> to see which repair gives back the most trips.</p>
      <button className="ghost small" onClick={close}>Got it</button>
      </>}
    </section>
  );
}
