import { setLang, useLang, type Lang } from "../i18n";

function Flag({ lang }: { lang: Lang }) {
  if (lang === "fr") {
    return (
      <svg viewBox="0 0 3 2" aria-hidden="true" focusable="false">
        <rect width="1" height="2" fill="#002654" /><rect x="1" width="1" height="2" fill="#fff" /><rect x="2" width="1" height="2" fill="#ce1126" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 60 30" aria-hidden="true" focusable="false">
      <clipPath id="uk-t"><path d="M30,15 h30 v15 z v15 h-30 z h-30 v-15 z v-15 h30 z" /></clipPath>
      <rect width="60" height="30" fill="#012169" />
      <path d="M0,0 L60,30 M60,0 L0,30" stroke="#fff" strokeWidth="6" />
      <path d="M0,0 L60,30 M60,0 L0,30" clipPath="url(#uk-t)" stroke="#C8102E" strokeWidth="4" />
      <path d="M30,0 v30 M0,15 h60" stroke="#fff" strokeWidth="10" />
      <path d="M30,0 v30 M0,15 h60" stroke="#C8102E" strokeWidth="6" />
    </svg>
  );
}

const NAME: Record<Lang, string> = { en: "English", fr: "Français" };

/** Language switch in the header: English / Français, remembered in this browser. */
export function LangSwitch() {
  const lang = useLang();
  return (
    <div className="langswitch" role="group" aria-label={lang === "fr" ? "Langue" : "Language"}>
      {(["en", "fr"] as Lang[]).map((l) => (
        <button key={l} lang={l} aria-pressed={lang === l} aria-label={`${l.toUpperCase()} — ${NAME[l]}`} title={NAME[l]}
                className={lang === l ? "on" : ""} onClick={() => setLang(l)}>
          <Flag lang={l} /><span>{l.toUpperCase()}</span>
        </button>
      ))}
    </div>
  );
}
