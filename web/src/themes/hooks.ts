import { useContext } from "react";

import { ThemeContext } from "./context-state";

export function useTheme() {
  return useContext(ThemeContext);
}
