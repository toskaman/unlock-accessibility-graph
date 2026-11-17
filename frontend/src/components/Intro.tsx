import { useState } from "react";

const KEY = "unlock.intro.dismissed";
const seen = () => { try { return localStorage.getItem(KEY) === "1"; } catch { return false; } };

/** Three lines that say what the page is, for a first-time visitor. */
export function Intro() {
  const [open, setOpen] = useState(() => !seen());
  if (!open) return null;
  const close = () => { setOpen(false); try { localStorage.setItem(KEY, "1"); } catch { /* ignore */ } };
  return (
    <section className="intro" aria-labelledby="intro-h">
      <h2 id="intro-h">Can a wheelchair user get there today?</h2>
      <p>Each dot is a station. The big number counts the station-to-station trips that can be made <strong>without a single step today</strong>, given which lifts actually work — red and amber dots are stations a broken lift cuts off.</p>
      <p>Check a trip, click a station to see where you can go from it, or open <em>Repairs that matter</em> to see which repair gives back the most trips.</p>
      <button className="ghost small" onClick={close}>Got it</button>
    </section>
  );
}
