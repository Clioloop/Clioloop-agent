import type { Metadata } from "next";
import Link from "next/link";
import DocsShell from "@/components/DocsShell";

export const metadata: Metadata = {
  title: "Getting started — install & connect Clioloop",
  description:
    "Install Clioloop on macOS, Linux or Windows and connect to 300+ models with one browser approval — no API keys. Step-by-step setup for the CLI and every other surface.",
  alternates: { canonical: "/docs/getting-started" },
};

export default function GettingStarted() {
  return (
    <DocsShell
      current="getting-started"
      title="Getting started"
      description="Install Clioloop and connect to 300+ models with one login."
    >
      <div className="docs-breadcrumb">
        <Link href="/docs">Docs</Link> / Getting started
      </div>
      <h1>Getting started</h1>
      <p>
        Clioloop installs in one line and connects to the Omni Loop Portal with a single
        browser approval — no API keys to copy. You&apos;ll be looping in under a minute.
      </p>

      <h2 id="install">1 · Install</h2>
      <p>
        <strong>macOS, Linux &amp; Termux</strong> — one command installs the CLI, terminal
        UI and desktop app:
      </p>
      <div className="code-block">
        <span className="c-cmd">curl -fsSL https://raw.githubusercontent.com/Clioloop/Clioloop-agent/main/scripts/install.sh | bash</span>
      </div>
      <p>
        <strong>Windows</strong> — install from PowerShell, or download the GUI installer{" "}
        <a href="https://github.com/Clioloop/Clioloop-agent/releases/latest/download/Clioloop-Setup.exe">
          Clioloop-Setup.exe
        </a>
        :
      </p>
      <div className="code-block">
        <span className="c-cmd">iex (irm https://raw.githubusercontent.com/Clioloop/Clioloop-agent/main/scripts/install.ps1)</span>
      </div>
      <div className="callout">
        The Windows installer isn&apos;t code-signed yet, so SmartScreen may warn
        &quot;Windows protected your PC.&quot; That&apos;s expected and harmless — click{" "}
        <strong>More info → Run anyway</strong>. Everything is open source and auditable
        on <a href="https://github.com/Clioloop/Clioloop-agent">GitHub</a>.
      </div>

      <h2 id="connect">2 · Connect</h2>
      <p>Run the setup wizard and choose <strong>Omni Loop Portal</strong>:</p>
      <div className="code-block">
        <span className="c-cmd">clio setup</span>
        <br />
        <span className="c-comment"># → choose &quot;Omni Loop Portal — one login, 300+ models&quot;</span>
      </div>
      <p>What happens next (an RFC 8628 device-code flow):</p>
      <ol>
        <li>
          Your browser opens this portal with a short device code like{" "}
          <code>WXYZ-2345</code>. No browser on this machine? The terminal prints a URL
          you can open on any device.
        </li>
        <li>Log in or sign up, check the code matches your terminal, and click Approve.</li>
        <li>
          The CLI receives its tokens automatically and shows the model picker — choose a
          default and you&apos;re connected.
        </li>
      </ol>
      <p>
        Prefer your own provider keys? The wizard can also store keys for Anthropic,
        OpenAI, Google and others — but the Portal is the no-key path.
      </p>

      <h2 id="first-loop">3 · Your first loop</h2>
      <p>Start an interactive session:</p>
      <div className="code-block">
        <span className="c-cmd">clio</span>
      </div>
      <p>Then try a few in-session commands:</p>
      <ul>
        <li><code>/help</code> — list every command in your build</li>
        <li><code>/model</code> — switch model or provider without restarting</li>
        <li><code>/goal build me a CLI todo app and test it</code> — start an autonomous loop</li>
      </ul>

      <h2 id="next">Where to next</h2>
      <ul>
        <li><Link href="/docs/fusion">Agentic Fusion</Link> — fuse a panel of models into one answer (Pro+).</li>
        <li><Link href="/docs/models">Models &amp; switching</Link> — work across 300+ models.</li>
        <li><Link href="/docs/surfaces">Surfaces</Link> — desktop, dashboard and chat apps.</li>
        <li><Link href="/docs/goals">Goals &amp; loops</Link> — keep the agent working until done.</li>
      </ul>
    </DocsShell>
  );
}
