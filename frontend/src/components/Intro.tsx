import { useState } from "react";
import { tr } from "../i18n";
import { StateMark } from "./Marks";

const KEY = "unlock.intro.dismissed";
const seen = () => { try { return localStorage.getItem(KEY) === "1"; } catch { return false; } };

/** One line that says how to read the map, with an easy-read version (FALC) for anyone who wants it simpler. */
export function Intro() {
  const [open, setOpen] = useState(() => !seen());
  const [easy, setEasy] = useState(false);
  if (!open) return null;
  const close = () => { setOpen(false); try { localStorage.setItem(KEY, "1"); } catch { /* ignore */ } };
  return (
    <section className="introline" aria-labelledby="intro-h">
      <p>
        <strong id="intro-h">{tr("Can a wheelchair user get there today?", "Peut-on y aller en fauteuil aujourd'hui ?")}</strong>{" "}
        {tr("Each mark is a station:", "Chaque marque est une gare :")}{" "}
        <span className="nowrap"><StateMark kind="open" /> {tr("open", "ouverte")}</span>,{" "}
        <span className="nowrap"><StateMark kind="doubt" /> {tr("only if a lift works", "seulement si un ascenseur marche")}</span>,{" "}
        <span className="nowrap"><StateMark kind="cut" /> {tr("cut off", "coupée")}</span>.
      </p>
      <div className="introline-actions">
        <button className="ghost small" aria-expanded={easy} aria-controls="easyread" onClick={() => setEasy(!easy)}>{tr("Easy read", "Facile à lire")}</button>
        <button className="ghost small" onClick={close}>{tr("Hide", "Masquer")}</button>
      </div>
      {easy && (
        <div id="easyread" className="easyread">
          <p>{tr("This map shows the train, metro and tram stations.", "Cette carte montre les gares de train, de métro et de tram.")}</p>
          <p>{tr("In some stations, a lift is broken.", "Dans certaines gares, un ascenseur est en panne.")}</p>
          <p>{tr("Without a lift, a person in a wheelchair cannot get through.", "Sans ascenseur, une personne en fauteuil ne peut pas passer.")}</p>
          <p><StateMark kind="open" /> {tr("A full dot: you can go.", "Un point plein : on peut y aller.")}{" "}
            <StateMark kind="doubt" /> {tr("A ring: maybe, if the lift works.", "Un rond vide : peut-être, si l'ascenseur marche.")}{" "}
            <StateMark kind="cut" /> {tr("A cross: you cannot.", "Une croix : on ne peut pas.")}</p>
        </div>
      )}
    </section>
  );
}
