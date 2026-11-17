import { useEffect, useState } from "react";
import { api } from "../api";
import type { Journey, SavedTrip, TripStatus } from "../types";

const STATIC_DEMO = import.meta.env.VITE_STATIC === "1";
const feed = (region: string, t: SavedTrip, fmt: "rss" | "ics") =>
  `${location.origin}/api/region/trips/feed.${fmt}?${new URLSearchParams({ from: t.from.id, to: t.to.id, region }).toString()}`;
const key = (region: string) => `unlock.trips.v1.${region}`;
const load = (region: string): SavedTrip[] => { try { return JSON.parse(localStorage.getItem(key(region)) || "[]"); } catch { return []; } };
const store = (region: string, t: SavedTrip[]) => { try { localStorage.setItem(key(region), JSON.stringify(t)); } catch { /* storage unavailable: keep in memory */ } };

const WORD: Record<string, { cls: string; label: string }> = {
  OK: { cls: "v-ok", label: "Step-free today" },
  DETOUR: { cls: "v-doubt", label: "Detour needed" },
  AT_RISK: { cls: "v-doubt", label: "At risk" },
  CUT: { cls: "v-cut", label: "Cut today" },
  NO_STEP_FREE_ROUTE: { cls: "v-none", label: "No step-free route" },
  UNKNOWN_STATION: { cls: "v-none", label: "Unknown station" },
};

/** Rider alerts: the rider's usual trips, kept in this browser only, re-checked against today's lift status. */
export function TripWatch({ region, journey, onError }: { region: string; journey: Journey | null; onError: (m: string) => void }) {
  const [trips, setTrips] = useState<SavedTrip[]>(() => load(region));
  const save = (t: SavedTrip[]) => store(region, t);
  const [status, setStatus] = useState<TripStatus[]>([]);

  const refresh = (list: SavedTrip[]) => {
    if (!list.length) { setStatus([]); return; }
    api.region.trips(list).then((r) => {
      setStatus(r.trips);
      const next = list.map((t, i) => ({ ...t, last_status: r.trips[i]?.status ?? t.last_status,
        usual: t.usual ?? r.trips[i]?.usual?.map(({ board, alight, line }) => ({ board, alight, line })) }));
      setTrips(next); save(next);
    }).catch((e) => onError(String(e?.message || e)));
  };
  useEffect(() => { refresh(trips); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const watched = journey && trips.some((t) => t.from.id === journey.from.id && t.to.id === journey.to.id);
  const add = () => {
    if (!journey) return;
    const next = [...trips, { from: { id: journey.from.id, name: journey.from.name }, to: { id: journey.to.id, name: journey.to.name } }].slice(-8);
    setTrips(next); save(next); refresh(next);
  };
  const remove = (i: number) => { const next = trips.filter((_, k) => k !== i); setTrips(next); save(next); setStatus(status.filter((_, k) => k !== i)); };
  const alerts = status.filter((s) => s.status !== "OK");

  return (
    <section className="tripwatch" aria-labelledby="twh">
      <h2 id="twh">My usual trips</h2>
      {journey && !watched && (
        <button className="ghost small" onClick={add}>Watch {journey.from.name} → {journey.to.name}</button>
      )}
      {!trips.length && <p className="muted small">Check a journey, then watch it: UNLOCK re-checks it against today's lift status each time you open this page. Your trips stay in this browser.</p>}
      {!!alerts.length && (
        <p className="tw-alert" role="status">{alerts.length === 1 ? "1 of your trips needs attention today." : `${alerts.length} of your trips need attention today.`}</p>
      )}
      <ul className="tw-list">
        {trips.map((t, i) => {
          const s = status[i];
          const w = s ? WORD[s.status] : null;
          return (
            <li key={t.from.id + t.to.id} className={w?.cls}>
              <div className="tw-row">
                <strong>{t.from.name} → {t.to.name}</strong>
                <button className="ghost small" aria-label={`Remove ${t.from.name} to ${t.to.name}`} onClick={() => remove(i)}>Remove</button>
              </div>
              {!STATIC_DEMO && (
                <p className="tiny tw-subs">Subscribe:{" "}
                  <a href={feed(region, t, "rss")}>RSS</a>{" · "}
                  <a href={feed(region, t, "ics").replace(/^https?:/, "webcal:")}>calendar</a>{" "}
                  <button className="linkish tiny" onClick={() => navigator.clipboard?.writeText(feed(region, t, "ics")).catch(() => undefined)}>copy calendar link</button>
                </p>
              )}
              {s ? <p className="small"><span className="tw-badge">{w?.label}</span>{s.changed && <span className="tw-changed"> changed since last check</span>} {s.message}</p>
                 : <p className="muted small">Checking…</p>}
            </li>
          );
        })}
      </ul>
      {!!status[0]?.observed && (
        <p className="muted tiny">Lift status read: SNCF {status[0].observed.sncf_lift_status?.slice(0, 16).replace("T", " ") ?? "—"}{status[0].observed.idfm_lift_status ? ` UTC · IDFM ${status[0].observed.idfm_lift_status.slice(0, 16).replace("T", " ")}` : ""} UTC.
          Also available from the command line (<code>python -m unlock alerts trips.json</code>) for a daily scheduled check.</p>
      )}
    </section>
  );
}
