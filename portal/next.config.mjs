/** @type {import('next').NextConfig} */

// Restrictive-but-functional CSP: Next.js inline runtime + styled JSX need
// 'unsafe-inline'; fonts are self-hosted via next/font; media may come from
// the CDN origin (MEDIA_BASE_URL, baked in at build time); everything else
// is same-origin.
const MEDIA_ORIGIN = process.env.MEDIA_BASE_URL
  ? new URL(process.env.MEDIA_BASE_URL).origin
  : null;
if (MEDIA_ORIGIN) console.log(`[portal] CSP media origin: ${MEDIA_ORIGIN}`);

const CSP = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "font-src 'self'",
  `img-src 'self' data:${MEDIA_ORIGIN ? ` ${MEDIA_ORIGIN}` : ""}`,
  `media-src 'self'${MEDIA_ORIGIN ? ` ${MEDIA_ORIGIN}` : ""}`,
  "connect-src 'self'",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self' https://checkout.stripe.com https://billing.stripe.com",
].join("; ");

const SECURITY_HEADERS = [
  { key: "Content-Security-Policy", value: CSP },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
  // Ignored over plain http (local/LAN installs), enforced on the real site.
  { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
];

const nextConfig = {
  serverExternalPackages: ["better-sqlite3"],
  outputFileTracingRoot: import.meta.dirname,
  poweredByHeader: false,
  async headers() {
    return [
      { source: "/:path*", headers: SECURITY_HEADERS },
      // The OAuth device-code + inference proxy endpoints are consumed by the
      // Clioloop CLI/TUI/desktop — never cache them.
      {
        source: "/api/:path*",
        headers: [{ key: "Cache-Control", value: "no-store" }],
      },
    ];
  },
};

export default nextConfig;
