import { useContext } from "react";

import { I18nContext } from "./state";

export function useI18n() {
  return useContext(I18nContext);
}
