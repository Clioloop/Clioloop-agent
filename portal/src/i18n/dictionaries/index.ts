import type { Locale } from "../locales";
import { en, type Dictionary } from "./en";
import { de } from "./de";
import { fr } from "./fr";
import { es } from "./es";
import { pt } from "./pt";
import { ja } from "./ja";
import { zh } from "./zh";

export type { Dictionary };
export { en };

export const DICTS: Record<Locale | "en", Dictionary> = { en, de, fr, es, pt, ja, zh };
