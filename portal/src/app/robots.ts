import type { MetadataRoute } from "next";

const SITE_URL = "https://portal.clioloop.com";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        // Keep auth, account and machine endpoints out of the index.
        disallow: ["/api/", "/dashboard", "/admin", "/activate", "/login", "/signup", "/forgot", "/reset"],
      },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
