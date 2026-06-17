import type { Metadata } from "next";
import Link from "next/link";
import DocsShell from "@/components/DocsShell";

export const metadata: Metadata = {
  title: "Security & tokens",
  description:
    "How Clioloop and the Omni Loop Portal keep you safe: device-code OAuth with no API keys, short-lived access tokens, single-use rotating refresh tokens with reuse detection, hashed storage, and read-only Fusion panels.",
  alternates: { canonical: "/docs/security" },
};

export default function SecurityDoc() {
  return (
    <DocsShell
      current="security"
      title="Security & tokens"
      description="Device-code OAuth, rotating single-use tokens and read-only fusion panels."
    >
      <div className="docs-breadcrumb">
        <Link href="/docs">Docs</Link> / Security &amp; tokens
      </div>
      <h1>Security &amp; tokens</h1>
      <p>
        The Omni Loop Portal is designed so there&apos;s nothing dangerous to leak. There
        are no standalone API keys — the only credential is a connected Clioloop device.
      </p>

      <h2 id="tokens">Tokens</h2>
      <ul>
        <li>Devices authenticate with short-lived access tokens (about 1 hour).</li>
        <li>Refresh tokens are single-use and rotate on every refresh.</li>
        <li>
          Refresh-token reuse is treated as theft: the whole device session family is
          revoked instantly (OAuth&nbsp;2.1 semantics). Lose a laptop, and replaying its
          old token kills the family.
        </li>
        <li>All tokens are stored hashed (SHA-256) — the portal never keeps plaintext credentials.</li>
      </ul>

      <h2 id="oauth">No API keys</h2>
      <p>
        Connecting uses an RFC&nbsp;8628 device-code flow: approve in the browser, and the
        agent receives rotating tokens automatically. See{" "}
        <Link href="/docs/getting-started">Getting started</Link> for the walkthrough.
      </p>

      <h2 id="fusion">Read-only Fusion panels</h2>
      <p>
        In <Link href="/docs/fusion">Agentic Fusion</Link>, planner and reviewer models are
        read-only <em>at the schema level</em> — write, shell and browser tools aren&apos;t
        in their toolset at all. They can research and critique, but only your main model
        can act, and you can watch it.
      </p>

      <h2 id="troubleshoot">Token troubleshooting</h2>
      <table>
        <thead>
          <tr><th>Error</th><th>What to do</th></tr>
        </thead>
        <tbody>
          <tr>
            <td><code>authorization_pending</code> forever</td>
            <td>The browser approval was never completed. Re-run login and approve at <code>/activate</code> within 15 minutes.</td>
          </tr>
          <tr>
            <td><code>card_verification_required</code></td>
            <td>Free-plan inference unlocks after the one-time €0 card verification — open your dashboard and click <strong>Verify card</strong>.</td>
          </tr>
          <tr>
            <td><code>refresh_token_reused</code></td>
            <td>An old refresh token was replayed (often a backup/restore of <code>~/.clio</code> across machines). Re-authenticate with <code>clio auth add managed</code>.</td>
          </tr>
        </tbody>
      </table>
    </DocsShell>
  );
}
