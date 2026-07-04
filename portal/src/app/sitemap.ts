import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/site";
import { LOCALES, langAlternates } from "@/i18n/locales";

// Public, indexable routes. Auth/app/api routes are intentionally excluded.
const ROUTES: { path: string; priority: number; changeFrequency: MetadataRoute.Sitemap[number]["changeFrequency"] }[] = [
  { path: "/", priority: 1.0, changeFrequency: "weekly" },
  { path: "/pricing", priority: 0.9, changeFrequency: "weekly" },
  { path: "/docs", priority: 0.9, changeFrequency: "weekly" },
  { path: "/docs/getting-started", priority: 0.8, changeFrequency: "monthly" },
  { path: "/docs/fusion", priority: 0.9, changeFrequency: "monthly" },
  { path: "/docs/goals", priority: 0.7, changeFrequency: "monthly" },
  { path: "/docs/models", priority: 0.7, changeFrequency: "monthly" },
  { path: "/docs/tools", priority: 0.7, changeFrequency: "monthly" },
  { path: "/docs/surfaces", priority: 0.7, changeFrequency: "monthly" },
  { path: "/docs/kanban", priority: 0.6, changeFrequency: "monthly" },
  { path: "/docs/skills", priority: 0.6, changeFrequency: "monthly" },
  { path: "/docs/security", priority: 0.6, changeFrequency: "monthly" },
  { path: "/docs/commands", priority: 0.7, changeFrequency: "monthly" },
  { path: "/docs/research", priority: 0.8, changeFrequency: "monthly" },
  { path: "/terms", priority: 0.3, changeFrequency: "yearly" },
  { path: "/privacy", priority: 0.3, changeFrequency: "yearly" },
];

/** hreflang alternates, absolute, for the two localized pages. */
function abs(path: "/" | "/pricing") {
  return Object.fromEntries(
    Object.entries(langAlternates(path)).map(([lang, p]) => [lang, `${SITE_URL}${p}`]),
  );
}

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  const entries: MetadataRoute.Sitemap = ROUTES.map((r) => ({
    url: `${SITE_URL}${r.path}`,
    lastModified: now,
    changeFrequency: r.changeFrequency,
    priority: r.priority,
    ...(r.path === "/" || r.path === "/pricing"
      ? { alternates: { languages: abs(r.path as "/" | "/pricing") } }
      : {}),
  }));
  for (const locale of LOCALES) {
    entries.push({
      url: `${SITE_URL}/${locale}`,
      lastModified: now,
      changeFrequency: "weekly",
      priority: 0.8,
      alternates: { languages: abs("/") },
    });
    entries.push({
      url: `${SITE_URL}/${locale}/pricing`,
      lastModified: now,
      changeFrequency: "weekly",
      priority: 0.7,
      alternates: { languages: abs("/pricing") },
    });
  }
  return entries;
}
