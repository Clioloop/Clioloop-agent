// Locales with fully translated landing + pricing pages, served under
// /{locale} and /{locale}/pricing via src/app/[locale]/.
// NOTE: any future top-level route named like a locale code would collide
// with the [locale] segment — static routes win, but avoid the ambiguity.
export const LOCALES = ["de", "fr", "es", "pt", "ja", "zh"] as const;
export type Locale = (typeof LOCALES)[number];

export const isLocale = (s: string): s is Locale =>
  (LOCALES as readonly string[]).includes(s);

export const LOCALE_LABELS: Record<Locale | "en", string> = {
  en: "English",
  de: "Deutsch",
  fr: "Français",
  es: "Español",
  pt: "Português",
  ja: "日本語",
  zh: "中文",
};

/** Reciprocal hreflang map for a localized path ("/" or "/pricing").
 *  Used identically on the English page and every locale page. */
export function langAlternates(path: "/" | "/pricing"): Record<string, string> {
  const suffix = path === "/" ? "" : path;
  const map: Record<string, string> = {
    "x-default": path,
    en: path,
  };
  for (const locale of LOCALES) map[locale] = `/${locale}${suffix}`;
  return map;
}
