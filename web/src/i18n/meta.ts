import type { Locale } from "./types";

// Display metadata for the language picker — endonym (native name) so users
// recognize their language even if they don't speak the current UI language.
//
// We intentionally do NOT pair locales with country flags. Languages are not
// countries (English ≠ GB, Portuguese ≠ PT, Spanish ≠ ES, Chinese variants ≠
// any single jurisdiction). Endonyms are unambiguous and avoid the political
// mismapping that flag pairings inevitably create.
export const LOCALE_META: Record<Locale, { name: string }> = {
  ar: { name: "العربية" },
  af: { name: "Afrikaans" },
  de: { name: "Deutsch" },
  en: { name: "English" },
  es: { name: "Español" },
  fr: { name: "Français" },
  ga: { name: "Gaeilge" },
  hu: { name: "Magyar" },
  it: { name: "Italiano" },
  ja: { name: "日本語" },
  ko: { name: "한국어" },
  pt: { name: "Português" },
  ru: { name: "Русский" },
  tr: { name: "Türkçe" },
  uk: { name: "Українська" },
  zh: { name: "简体中文" },
  "zh-hant": { name: "繁體中文" },
};
