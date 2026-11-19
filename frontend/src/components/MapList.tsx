import { useMemo } from "react";
import { num, tr } from "../i18n";
import type { ReachClass, RegionStation } from "../types";
import { StateMark, type MarkKind } from "./Marks";

type Group = { key: string; title: string; mark: MarkKind; ids: RegionStation[]; open: boolean };

/** The map as a list, for screen readers, keyboards and anyone who prefers text: stations grouped by state
 *  (or, after a click on a station, by where you can go from it). Each name selects the station. */
export function MapList({ stations, reach, onSelect }: {
  stations: RegionStation[]; reach: { origin: string; originName: string; classes: Record<string, ReachClass> } | null; onSelect: (id: string) => void;
}) {
  const groups = useMemo<Group[]>(() => {
    const by = (f: (s: RegionStation) => boolean) => stations.filter(f).sort((a, b) => a.name.localeCompare(b.name));
    if (reach) {
      const c = (s: RegionStation) => reach.classes[s.id];
      return [
        { key: "CUT", title: tr("Cut by outages", "Coupées par des pannes"), mark: "cut", ids: by((s) => c(s) === "CUT"), open: true },
        { key: "IF", title: tr("Only if listed lifts work", "Seulement si les ascenseurs signalés fonctionnent"), mark: "doubt", ids: by((s) => c(s) === "IF_LIFTS_WORK"), open: true },
        { key: "OK", title: tr("Reachable without a step", "Accessibles sans marche"), mark: "ok", ids: by((s) => c(s) === "CONFIRMED"), open: false },
      ];
    }
    return [
      { key: "CLOSED", title: tr("Cut off", "Coupées"), mark: "cut", ids: by((s) => s.state === "CLOSED"), open: true },
      { key: "DOUBT", title: tr("A lift is reported out", "Un ascenseur est signalé en panne"), mark: "doubt", ids: by((s) => s.state === "DOUBT"), open: true },
      { key: "OPEN", title: tr("Open without a step", "Ouvertes sans marche"), mark: "open", ids: by((s) => s.state === "OPEN"), open: false },
    ];
  }, [stations, reach]);
  const none = stations.filter((s) => s.state === "NOT_BOARDABLE").length;
  return (
    <section className="maplist" id="maplist" aria-labelledby="maplist-h">
      <h2 id="maplist-h">{reach ? tr(`Where you can go from ${reach.originName}`, `Où aller depuis ${reach.originName}`) : tr("Stations by state", "Les gares selon leur état")}</h2>
      {groups.map((g) => (
        <details key={g.key} open={g.open && g.ids.length <= 60}>
          <summary><StateMark kind={g.mark} /> {g.title} <span className="count">({num(g.ids.length)})</span></summary>
          {g.ids.length ? (
            <ul>{g.ids.map((s) => <li key={s.id}><button className="linkish plain" onClick={() => onSelect(s.id)}>{s.name}</button></li>)}</ul>
          ) : <p className="muted">{tr("None.", "Aucune.")}</p>}
        </details>
      ))}
      {!reach && none > 0 && <p className="muted">{tr(`${num(none)} other stations have no platform declared wheelchair-accessible.`, `${num(none)} autres gares n'ont aucun quai déclaré accessible en fauteuil.`)}</p>}
    </section>
  );
}
