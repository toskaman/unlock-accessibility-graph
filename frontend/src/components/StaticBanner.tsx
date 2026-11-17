import { useEffect, useState } from "react";
import { relate, snapshotMeta, type RelateInfo } from "../static/staticApi";
import { fmtDate, isFr, num } from "../i18n";

const REPO = "https://github.com/toskaman/unlock-accessibility-graph";
const fmt = (s?: string | null) => (s ? fmtDate(new Date(s), { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Paris" }) + (isFr() ? " heure de Paris" : " Paris") : "—");

/** Zero-install demo: says what this page is (a snapshot) and shows Relate running in the browser. */
export function StaticBanner({ region }: { region: string }) {
  const [info, setInfo] = useState<RelateInfo | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [meta, setMeta] = useState<{ exported_at: string; lift_status: Record<string, { sncf: string | null; idfm: string | null }> } | null>(null);
  useEffect(() => { snapshotMeta().then(setMeta).catch(() => undefined); }, []);
  useEffect(() => {
    setInfo(null); setErr(null);
    relate(region).then(setInfo).catch((e) => setErr(String(e?.message || e)));
  }, [region]);
  const ls = meta?.lift_status[region];
  return (
    <div className="banner static-banner" role="note">
      {isFr() ? <p><strong>Démo sans installation.</strong> Un instantané exporté des bases Relate d'UNLOCK (état des ascenseurs : SNCF {fmt(ls?.sncf)}{ls?.idfm ? `, IDFM ${fmt(ls.idfm)}` : ""}).
        Trajets, accessibilité depuis une gare et alertes sont calculés dans cette page ;{" "}
        {info ? <>chaque tronçon et chaque calcul d'accessibilité est revérifié par <strong>Relate {info.version}, qui tourne en WebAssembly dans votre navigateur</strong> ({num(info.counts.stations)} gares, {num(info.counts.platforms)} quais, {num(info.counts.legs)} tronçons LEG chargés en {num(info.load_ms)} ms).</>
          : err ? <>Relate (WebAssembly) n'a pas pu démarrer ici ({err}) ; les résultats sont quand même calculés, sans la revérification dans le navigateur.</>
          : <>Relate (WebAssembly) se charge dans votre navigateur pour revérifier chaque tronçon…</>}
        {" "}L'état des ascenseurs en direct, la vue intérieure des gares et les simulations de panne demandent l'application installée : <a href={REPO}>{REPO.replace("https://", "")}</a>.</p>
      : <p><strong>Zero-install demo.</strong> A snapshot exported from UNLOCK's Relate stores (lift status: SNCF {fmt(ls?.sncf)}{ls?.idfm ? `, IDFM ${fmt(ls.idfm)}` : ""}).
        Journeys, reaches and trip alerts are computed in this page; {" "}
        {info ? <>every leg and every reach is re-checked by <strong>Relate {info.version} running as WebAssembly in your browser</strong> ({num(info.counts.stations)} stations, {num(info.counts.platforms)} platforms, {num(info.counts.legs)} LEG rides loaded in {info.load_ms} ms).</>
          : err ? <>Relate (WebAssembly) could not start here ({err}); results are still computed, without the in-browser re-check.</>
          : <>Relate (WebAssembly) is loading in your browser to re-check every leg and reach…</>}
        {" "}Live lift status, the station cross-sections and outage simulations need the installed app: <a href={REPO}>{REPO.replace("https://", "")}</a>.</p>}
    </div>
  );
}
