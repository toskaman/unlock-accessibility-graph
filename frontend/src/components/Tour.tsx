import { useState } from "react";
import { tr } from "../i18n";

const KEY = "unlock.tour.done";
const done = () => { try { return localStorage.getItem(KEY) === "1"; } catch { return true; } };

/** First visit only: three short steps on how to read the page. Can be skipped; never shown again once closed. */
export function Tour() {
  const [step, setStep] = useState(() => (done() ? -1 : 0));
  if (step < 0) return null;
  const steps = [
    { t: tr("Today's number", "Le chiffre du jour"), b: tr("The dark plate on the map: how many station-to-station trips a wheelchair user can make today without a single step — and how many are not certain.", "La plaque sombre sur la carte : combien de trajets de gare à gare on peut faire aujourd'hui en fauteuil sans une seule marche — et combien ne sont pas garantis.") },
    { t: tr("Where can I go from here?", "Où puis-je aller d'ici ?"), b: tr("Click any station: the map shows where you can go from it. We opened the station where one repair matters most. Try “If the broken lifts worked…”.", "Cliquez une gare : la carte montre où l'on peut aller depuis elle. Nous avons ouvert la gare où une réparation compte le plus. Essayez « Si les ascenseurs en panne marchaient… ».") },
    { t: tr("Fix what matters first", "Réparer d'abord ce qui compte"), b: tr("On the right: each broken lift and how many trips it gives back once fixed. On the left: check your own trip.", "À droite : chaque ascenseur en panne et le nombre de trajets qu'il rend une fois réparé. À gauche : vérifiez votre propre trajet.") },
  ];
  const close = () => { setStep(-1); try { localStorage.setItem(KEY, "1"); } catch { /* ignore */ } };
  const s = steps[step];
  return (
    <aside className="tour" role="dialog" aria-modal="false" aria-labelledby="tour-t">
      <p className="tour-k">{tr(`Quick tour · ${step + 1} of 3`, `Visite rapide · ${step + 1} sur 3`)}</p>
      <h2 id="tour-t">{s.t}</h2>
      <p>{s.b}</p>
      <div className="tour-a">
        <button className="ghost small" onClick={close}>{tr("Skip", "Passer")}</button>
        {step < 2 ? <button className="primary small" onClick={() => setStep(step + 1)}>{tr("Next", "Suivant")}</button>
          : <button className="primary small" onClick={close}>{tr("Got it", "Compris")}</button>}
      </div>
    </aside>
  );
}
