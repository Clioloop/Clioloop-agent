import { ar } from './ar'
import { en } from './en'
import type { Locale, Translations } from './types'
import { zh } from './zh'

export const TRANSLATIONS: Record<Locale, Translations> = {
  ar,
  en,
  zh
}
