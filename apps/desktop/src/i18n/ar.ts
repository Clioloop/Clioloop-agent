import { en } from './en'
import type { Translations } from './types'

// Full contract fallback with translated shared shell copy. This keeps every
// existing surface available while Arabic coverage grows incrementally.
export const ar: Translations = {
  ...en,
  common: {
    ...en.common,
    save: 'حفظ',
    saving: 'جارٍ الحفظ',
    cancel: 'إلغاء',
    close: 'إغلاق',
    confirm: 'تأكيد',
    delete: 'حذف',
    refresh: 'تحديث',
    retry: 'إعادة المحاولة'
  },
  language: {
    ...en.language,
    label: 'اللغة',
    description: 'اختر لغة عرض Clio',
    saving: 'جارٍ حفظ اللغة',
    saveError: 'تعذر حفظ اللغة'
  }
}