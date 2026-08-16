import { en } from "./en";
import type { Translations } from "./types";

// Keep the complete English contract as a fallback while Arabic copy expands.
// Product and organization names deliberately remain Clio / Omni Loop Labs.
export const ar: Translations = {
  ...en,
  common: {
    ...en.common,
    save: "حفظ",
    cancel: "إلغاء",
    close: "إغلاق",
    confirm: "تأكيد",
    delete: "حذف",
    refresh: "تحديث",
    retry: "إعادة المحاولة",
    search: "بحث...",
    loading: "جارٍ التحميل...",
  },
  app: {
    ...en.app,
    closeNavigation: "إغلاق التنقل",
    navigation: "التنقل",
    openNavigation: "فتح التنقل",
    nav: {
      ...en.app.nav,
      analytics: "التحليلات",
      chat: "الدردشة",
      config: "الإعدادات",
      documentation: "التوثيق",
      plugins: "الإضافات",
      sessions: "الجلسات",
      skills: "المهارات",
    },
  },
};