import type { Metadata } from "next";

export const metadata: Metadata = { title: "Docs & Tutorials — Omni Loop Portal" };

function Code({ children }: { children: React.ReactNode }) {
  return <div className="code-block">{children}</div>;
}

export default function DocsPage() {
  return (
    <div className="page">
      <div className="container">
        <div className="docs-layout">
          <aside className="docs-toc">
            <a href="#getting-started">Getting started</a>
            <a href="#connect-cli">Tutorial: CLI</a>
            <a href="#connect-tui">Tutorial: TUI</a>
            <a href="#connect-desktop">Tutorial: Desktop app</a>
            <a href="#connect-dashboard">Tutorial: Web dashboard</a>
            <a href="#tool-gateway">The Tool Gateway</a>
            <a href="#models">Models & switching</a>
            <a href="#plans">Plans & usage</a>
            <a href="#security">Security & tokens</a>
            <a href="#troubleshooting">Troubleshooting</a>
          </aside>

          <article className="docs-content fade-up">
            <h2 id="getting-started">Getting started</h2>
            <p>
              Omni Loop Portal is the subscription gateway for{" "}
              <a href="https://github.com/Clioloop/Clioloop-agent">Clioloop</a> — and
              only for Clioloop. Instead of collecting API keys from half a dozen
              vendors, you log in once and your agent gets 300+ models plus the Tool
              Gateway: web search, image &amp; video generation, text-to-speech and a
              cloud browser, all billed against one subscription.
            </p>
            <ol>
              <li>
                <strong>Create an account</strong> — sign up and pick a plan (Free works,
                it just needs a one-time card verification).
              </li>
              <li>
                <strong>Install Clioloop</strong> if you haven&apos;t:
              </li>
            </ol>
            <Code>
              <span className="c-cmd">
                curl -fsSL
                https://raw.githubusercontent.com/Clioloop/Clioloop-agent/main/scripts/install.sh
                | bash
              </span>
            </Code>
            <p>
              On <strong>Windows</strong>, download and run the installer instead:{" "}
              <a href="https://github.com/Clioloop/Clioloop-agent/releases/latest/download/Clioloop-Setup.exe">
                Clioloop-Setup.exe
              </a>
              . It isn&apos;t code-signed yet, so SmartScreen may warn with &quot;Windows
              protected your PC&quot; — that&apos;s expected and harmless; click{" "}
              <strong>More info → Run anyway</strong>. The whole project is open source
              and auditable on{" "}
              <a href="https://github.com/Clioloop/Clioloop-agent">GitHub</a>.
            </p>
            <ol start={3}>
              <li>
                <strong>Connect a surface</strong> — follow any tutorial below. They all
                use the same one-click device login.
              </li>
            </ol>

            <h2 id="connect-cli">Tutorial: connect the CLI</h2>
            <p>The quick setup makes Omni Loop Portal the first option:</p>
            <Code>
              <span className="c-cmd">clio setup</span>
              <br />
              <span className="c-comment">
                # → choose &quot;Omni Loop Portal — one login, 300+ models&quot;
              </span>
            </Code>
            <p>What happens next:</p>
            <ol>
              <li>
                Your browser opens this portal with a device code like{" "}
                <code>WXYZ-2345</code> (no browser available? The terminal prints the URL
                to open on any device).
              </li>
              <li>Log in, check the code matches your terminal, click Approve.</li>
              <li>
                The CLI receives its tokens automatically and shows the model picker —
                choose a default and you&apos;re done.
              </li>
            </ol>
            <p>Already set up and just want to add the portal as a provider?</p>
            <Code>
              <span className="c-cmd">clio auth add managed</span>{" "}
              <span className="c-comment"># direct device login</span>
              <br />
              <span className="c-cmd">clio model</span>{" "}
              <span className="c-comment"># switch provider/model anytime</span>
            </Code>

            <h2 id="connect-tui">Tutorial: connect the TUI</h2>
            <p>
              The terminal UI shares credentials with the CLI — connecting once connects
              both. Inside <code>clio</code> (the TUI), use the model switcher:
            </p>
            <ul>
              <li>
                Type <code>/model</code> and pick <strong>Omni Loop Portal</strong> from
                the provider list, or
              </li>
              <li>
                run <code>clio setup --portal</code> from a shell for the one-shot portal
                setup.
              </li>
            </ul>
            <p>
              The device login flow is identical: approve in the browser, come back, pick
              a model.
            </p>

            <h2 id="connect-desktop">Tutorial: connect the desktop app</h2>
            <ol>
              <li>
                Launch the app with <code>clio desktop</code> (or the installed
                shortcut).
              </li>
              <li>
                Open <strong>Settings → Providers</strong> and click{" "}
                <strong>Connect Omni Loop Portal</strong>.
              </li>
              <li>
                Your browser opens with the device code pre-filled — approve, and the app
                refreshes with the portal&apos;s model catalog.
              </li>
            </ol>

            <h2 id="connect-dashboard">Tutorial: connect the web dashboard</h2>
            <ol>
              <li>
                Start the dashboard: <code>clio dashboard</code>
              </li>
              <li>
                Open the <strong>Omni Portal</strong> page in the sidebar and click{" "}
                <strong>Connect</strong>.
              </li>
              <li>
                Approve the device code in the tab that opens. The dashboard then shows
                your plan, usage and the models you can use.
              </li>
            </ol>

            <h2 id="tool-gateway">The Tool Gateway</h2>
            <p>
              Beyond models, your subscription bundles the agent services Clioloop uses
              every day. There is nothing to configure — once a device is connected,
              entitled tools route through the portal automatically:
            </p>
            <ul>
              <li>
                <strong>Web search &amp; extract</strong> — the{" "}
                <code>web_search</code> and <code>web_extract</code> tools, all plans.
              </li>
              <li>
                <strong>Image generation</strong> — fast, high-quality images, paid
                plans.
              </li>
              <li>
                <strong>Premium TTS</strong> — studio-quality voices for voice replies,
                paid plans (a free local voice is always available).
              </li>
              <li>
                <strong>Cloud browser</strong> — hosted browser sessions for
                automation, paid plans.
              </li>
              <li>
                <strong>Video generation</strong> — Max and Max 10x plans.
              </li>
            </ul>
            <p>
              Check what your plan includes under <strong>dashboard → Tool Gateway</strong>,
              or pick the &quot;Omni Loop Portal Subscription&quot; rows in{" "}
              <code>clio tools</code>. Gateway calls are metered against the same monthly
              allowance as inference.
            </p>
            <p>
              Note: the portal does not issue standalone API keys. The only credential it
              accepts is the Clioloop device login — connect a device and let the agent
              do the talking.
            </p>

            <h2 id="models">Models &amp; switching</h2>
            <p>
              Most model IDs use <code>vendor/model</code> naming, e.g.{" "}
              <code>anthropic/claude-sonnet-4.6</code>, <code>openai/gpt-5.2</code>,{" "}
              <code>deepseek/deepseek-v3.2</code>. In any Clioloop surface:
            </p>
            <ul>
              <li>
                <code>/model</code> — interactive picker with live pricing
              </li>
              <li>
                <code>clio -m vendor/model</code> — one-off model for a session
              </li>
            </ul>
            <p>
              Free-plan accounts see the community catalog (models ending in{" "}
              <code>:free</code>). Paid plans see everything.
            </p>

            <h2 id="plans">Plans &amp; usage</h2>
            <table>
              <thead>
                <tr>
                  <th>Plan</th>
                  <th>Price</th>
                  <th>Models</th>
                  <th>Tool Gateway</th>
                  <th>Monthly usage</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Free</td>
                  <td>€0 (card verification)</td>
                  <td>1 free model</td>
                  <td>Web search</td>
                  <td>Starter allowance</td>
                </tr>
                <tr>
                  <td>Pro</td>
                  <td>€20/mo</td>
                  <td>Large open-model catalog</td>
                  <td>Web · image · TTS · browser</td>
                  <td>Baseline (1×)</td>
                </tr>
                <tr>
                  <td>Max</td>
                  <td>€100/mo</td>
                  <td>300+ frontier models</td>
                  <td>Everything + video</td>
                  <td>5× Pro</td>
                </tr>
                <tr>
                  <td>Max 10x</td>
                  <td>€250/mo</td>
                  <td>300+ frontier models</td>
                  <td>Everything + video</td>
                  <td>10× Pro</td>
                </tr>
              </tbody>
            </table>
            <p>
              Usage is metered at the upstream model&apos;s real cost per request and
              resets on the 1st of each month (UTC). The dashboard shows a live meter;
              when an allowance runs out the API returns a clear{" "}
              <code>quota_exhausted</code> error and Clioloop tells you how to upgrade.
            </p>

            <h2 id="security">Security &amp; tokens</h2>
            <ul>
              <li>
                Devices authenticate with short-lived access tokens (1 hour) and
                single-use rotating refresh tokens.
              </li>
              <li>
                Refresh-token reuse is treated as theft: the whole device session family
                is revoked instantly (OAuth 2.1 semantics).
              </li>
              <li>All tokens are stored hashed (SHA-256) — the portal never keeps plaintext credentials.</li>
              <li>
                There are no standalone API keys to leak — the portal only speaks to
                connected Clioloop devices.
              </li>
            </ul>

            <h2 id="troubleshooting">Troubleshooting</h2>
            <h3>&quot;authorization_pending&quot; forever</h3>
            <p>
              The browser approval was never completed. Re-run the login and approve the
              code at <code>/activate</code> within 15 minutes.
            </p>
            <h3>&quot;card_verification_required&quot;</h3>
            <p>
              Free-plan inference unlocks after the one-time €0 card verification — open
              your dashboard and click <strong>Verify card</strong>.
            </p>
            <h3>&quot;refresh_token_reused&quot;</h3>
            <p>
              Something replayed an old refresh token (often a backup/restore of{" "}
              <code>~/.clio</code> across machines). Re-authenticate with{" "}
              <code>clio auth add managed</code>.
            </p>
            <h3>Model not available</h3>
            <p>
              Free plans include one free model. If a model disappears from the
              catalog, it may have been retired upstream — run{" "}
              <code>/model</code> to pick a current one.
            </p>
          </article>
        </div>
      </div>
    </div>
  );
}
