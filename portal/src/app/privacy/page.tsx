import type { Metadata } from "next";

export const metadata: Metadata = { title: "Privacy Policy — Omni Loop Portal" };

export default function PrivacyPage() {
  return (
    <div className="page">
      <div className="container" style={{ maxWidth: 760 }}>
        <article className="docs-content fade-up">
          <span className="eyebrow">legal</span>
          <h1 style={{ marginTop: 18 }}>Privacy Policy</h1>
          <p>Last updated: June 12, 2026</p>

          <h2>What we collect</h2>
          <ul>
            <li>
              <strong>Account data</strong> — email, display name, and a bcrypt hash
              of your password (never the password itself).
            </li>
            <li>
              <strong>Billing data</strong> — handled by Stripe; we store only your
              Stripe customer reference, plan, and subscription status. Card numbers
              never touch our servers.
            </li>
            <li>
              <strong>Usage metering</strong> — per-request model name, token counts
              and cost, kept to enforce monthly allowances and show your dashboard.
            </li>
            <li>
              <strong>Device credentials</strong> — OAuth tokens for connected
              Clioloop devices, stored as SHA-256 hashes only.
            </li>
          </ul>

          <h2>What we don&apos;t collect</h2>
          <p>
            We do not store the content of your prompts, completions, web searches,
            or other tool traffic. Requests are proxied to the upstream provider and
            only the metering metadata above is retained.
          </p>

          <h2>Third parties</h2>
          <p>
            Your requests are forwarded to upstream providers as needed to serve
            them: OpenRouter (model inference), Firecrawl (web search), Browser Use
            (cloud browser), FAL (image/video), Stripe (payments) and Resend
            (transactional email). Each processes data under its own privacy policy.
          </p>

          <h2>Retention &amp; deletion</h2>
          <p>
            Account and metering data is kept while your account exists. Email us to
            delete your account; backups expire within 14 days. Action tokens
            (verification/reset links) are single-use and expire automatically.
          </p>

          <h2>Where</h2>
          <p>
            Servers are located in the EU (Germany); transactional email is sent from
            an EU region. We use no advertising or analytics trackers — the only
            cookie is your login session.
          </p>

          <h2>Contact</h2>
          <p>
            Privacy requests: <a href="mailto:noreply@clioloop.com">noreply@clioloop.com</a>
          </p>
        </article>
      </div>
    </div>
  );
}
