import { createContext } from "react";

import { af } from "./af";
import { de } from "./de";
import { en } from "./en";
import { es } from "./es";
import { fr } from "./fr";
import { ga } from "./ga";
import { hu } from "./hu";
import { it } from "./it";
import { ja } from "./ja";
import { ko } from "./ko";
import { pt } from "./pt";
import { ru } from "./ru";
import { tr } from "./tr";
import type { Locale, Translations } from "./types";
import { uk } from "./uk";
import { zh } from "./zh";
import { zhHant } from "./zh-hant";

export const TRANSLATIONS: Record<Locale, Translations> = {
  af,
  de,
  en,
  es,
  fr,
  ga,
  hu,
  it,
  ja,
  ko,
  pt,
  ru,
  tr,
  uk,
  zh,
  "zh-hant": zhHant,
};

export interface I18nContextValue {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: Translations;
}

export const I18nContext = createContext<I18nContextValue>({
  locale: "en",
  setLocale: () => {},
  t: en,
});

const SUPPORTED_LOCALES = Object.keys(TRANSLATIONS) as Locale[];
const STORAGE_KEY = "clio-locale";

function isLocale(value: string): value is Locale {
  return (SUPPORTED_LOCALES as string[]).includes(value);
}

export function getInitialLocale(): Locale {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);

    if (stored && isLocale(stored)) {
      return stored;
    }
  } catch {
    // SSR or privacy mode
  }

  return "en";
}

export function persistLocale(locale: Locale): void {
  try {
    localStorage.setItem(STORAGE_KEY, locale);
  } catch {
    // ignore
  }
}
