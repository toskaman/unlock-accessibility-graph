import { useSyncExternalStore } from "react";

/** English / French. The choice comes from ?lang=, then this browser's last choice, then the browser language.
 *  Strings are written in place, in both languages: tr("English", "Français"). */
export type Lang = "en" | "fr";
const KEY = "unlock.lang";

function initial(): Lang {
  try {
    const q = new URLSearchParams(location.search).get("lang");
    if (q === "fr" || q === "en") return q;
    const s = localStorage.getItem(KEY);
    if (s === "fr" || s === "en") return s;
  } catch { /* storage or location unavailable */ }
  return typeof navigator !== "undefined" && /^fr\b/i.test(navigator.language || "") ? "fr" : "en";
}

let current: Lang = initial();
const listeners = new Set<() => void>();

function apply() {
  document.documentElement.lang = current;
  document.title = current === "fr" ? "UNLOCK — l'accessibilité en fauteuil, ascenseur par ascenseur" : "UNLOCK — The Accessibility Impact Graph";
}
if (typeof document !== "undefined") apply();

export const getLang = () => current;
export const isFr = () => current === "fr";
export const tr = (en: string, fr: string) => (current === "fr" ? fr : en);
export const locale = () => (current === "fr" ? "fr-FR" : "en-GB");

export function setLang(l: Lang) {
  if (l === current) return;
  current = l;
  try { localStorage.setItem(KEY, l); } catch { /* ignore */ }
  try {
    const u = new URL(location.href);
    if (u.searchParams.has("lang")) { u.searchParams.set("lang", l); history.replaceState(history.state, "", u); }
  } catch { /* ignore */ }
  apply();
  listeners.forEach((f) => f());
}

export function useLang(): Lang {
  return useSyncExternalStore((f) => { listeners.add(f); return () => listeners.delete(f); }, () => current, () => current);
}

/** Numbers: 231,883 in English, 231 883 in French. */
export const num = (x: number | undefined | null) => (x == null ? "—" : x.toLocaleString(locale()));
/** "s" when plural, in both languages (enough for the words used here). */
export const pl = (n: number, word: string) => (n > 1 ? `${word}s` : word);
/** Dates and times in the current language. */
export const fmtDate = (d: Date, o: Intl.DateTimeFormatOptions) => d.toLocaleString(locale(), o);
export const fmtDay = (d: Date, o: Intl.DateTimeFormatOptions) => d.toLocaleDateString(locale(), o);

/** Labels of the network kinds stored with each region. */
export const netLabel = (s?: string | null) =>
  !s || current === "en" ? s || "" : s === "IDFM rail, metro, tram" ? "RER, Transilien, métro et tram (IDFM)"
    : s.startsWith("SNCF trains") ? "trains SNCF (TER, Intercités, TGV)" : s;
