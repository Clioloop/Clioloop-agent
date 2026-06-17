import type { MetadataRoute } from "next";

const SITE_URL = "https://portal.clioloop.com";

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
  { path: "/terms", priority: 0.3, changeFrequency: "yearly" },
  { path: "/privacy", priority: 0.3, changeFrequency: "yearly" },
];

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  return ROUTES.map((r) => ({
    url: `${SITE_URL}${r.path}`,
    lastModified: now,
    changeFrequency: r.changeFrequency,
    priority: r.priority,
  }));
}
