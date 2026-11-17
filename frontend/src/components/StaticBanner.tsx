import { useEffect, useState } from "react";
import { relate, snapshotMeta, type RelateInfo } from "../static/staticApi";

const REPO = "https://github.com/toskaman/unlock-accessibility-graph";
const fmt = (s?: string | null) => (s ? new Date(s).toLocaleString("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Paris" }) + " Paris" : "—");

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
      <p><strong>Zero-install demo.</strong> A snapshot exported from UNLOCK's Relate stores (lift status: SNCF {fmt(ls?.sncf)}{ls?.idfm ? `, IDFM ${fmt(ls.idfm)}` : ""}).
        Journeys, reaches and trip alerts are computed in this page; {" "}
        {info ? <>every leg and every reach is re-checked by <strong>Relate {info.version} running as WebAssembly in your browser</strong> ({info.counts.stations.toLocaleString("en-GB")} stations, {info.counts.platforms.toLocaleString("en-GB")} platforms, {info.counts.legs.toLocaleString("en-GB")} LEG rides loaded in {info.load_ms} ms).</>
          : err ? <>Relate (WebAssembly) could not start here ({err}); results are still computed, without the in-browser re-check.</>
          : <>Relate (WebAssembly) is loading in your browser to re-check every leg and reach…</>}
        {" "}Live lift status, the station cross-sections and outage simulations need the installed app: <a href={REPO}>{REPO.replace("https://", "")}</a>.</p>
    </div>
  );
}
