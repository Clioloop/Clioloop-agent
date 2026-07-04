// Canonical site origin. PORTAL_BASE_URL lets preview/staging deploys emit
// their own URLs in metadata, sitemap and robots (all baked at build time).
export const SITE_URL = (process.env.PORTAL_BASE_URL?.trim() || "https://portal.clioloop.com").replace(
  /\/+$/,
  "",
);
