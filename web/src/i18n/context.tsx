import { useCallback, useEffect, useState, type ReactNode } from "react";

import {
  getInitialLocale,
  I18nContext,
  persistLocale,
  TRANSLATIONS,
  type I18nContextValue,
} from "./state";
import type { Locale } from "./types";

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(getInitialLocale);

  useEffect(() => {
    const root = document.documentElement;
    root.lang = locale;
    root.dir = locale === "ar" ? "rtl" : "ltr";
  }, [locale]);

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l);
    persistLocale(l);
  }, []);

  const value: I18nContextValue = {
    locale,
    setLocale,
    t: TRANSLATIONS[locale],
  };

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}
