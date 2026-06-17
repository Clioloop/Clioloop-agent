import type { Metadata } from "next";
import Link from "next/link";
import DocsShell from "@/components/DocsShell";

export const metadata: Metadata = {
  title: "Surfaces — CLI, TUI, desktop, dashboard & chat apps",
  description:
    "Run Clioloop anywhere: the CLI, a full terminal UI, an Electron desktop app, a web dashboard, and a messaging gateway for Telegram, Slack, WhatsApp, Discord and more — all sharing one account, session and memory.",
  alternates: { canonical: "/docs/surfaces" },
};

export default function SurfacesDoc() {
  return (
    <DocsShell
      current="surfaces"
      title="Surfaces"
      description="CLI, terminal UI, desktop, web dashboard and messaging gateways — one account."
    >
      <div className="docs-breadcrumb">
        <Link href="/docs">Docs</Link> / Surfaces
      </div>
      <h1>Surfaces</h1>
      <p>
        Clioloop runs wherever you work. Every surface shares the same account, session
        and memory — connect once and pick up the same conversation from your terminal,
        your desktop or your phone.
      </p>

      <h2 id="cli">CLI &amp; terminal UI</h2>
      <p>
        <code>clio</code> on its own starts an interactive chat with markdown, syntax
        highlighting and inline images. <code>clio --tui</code> launches the full
        React-Ink terminal UI.
      </p>
      <div className="code-block">
        <span className="c-cmd">clio</span>{" "}
        <span className="c-comment"># interactive chat</span>
        <br />
        <span className="c-cmd">clio --tui</span>{" "}
        <span className="c-comment"># full terminal UI</span>
      </div>

      <h2 id="desktop">Desktop app</h2>
      <p>
        A cross-platform Electron app with a system tray, the Kanban board and live goal
        banners:
      </p>
      <div className="code-block">
        <span className="c-cmd">clio desktop</span>
      </div>
      <p>
        Connect under <strong>Settings → Providers → Connect Omni Loop Portal</strong> —
        the same one-click device login.
      </p>

      <h2 id="dashboard">Web dashboard</h2>
      <p>A browser dashboard for plan, usage, connected devices and the task board:</p>
      <div className="code-block">
        <span className="c-cmd">clio dashboard</span>
      </div>

      <h2 id="gateway">Messaging gateway</h2>
      <p>
        The gateway lets you drive the agent from chat apps — the same session and memory,
        on your phone:
      </p>
      <div className="code-block">
        <span className="c-cmd">clio gateway</span>{" "}
        <span className="c-comment"># Telegram, Slack, WhatsApp, Discord and more</span>
        <br />
        <span className="c-cmd">clio send</span>{" "}
        <span className="c-comment"># message a channel from a script</span>
      </div>
      <p>
        Adapters exist for Telegram, Slack, Discord, WhatsApp, Signal, Matrix, email,
        Home Assistant and others. Slash commands work in chat too.
      </p>

      <div className="callout">
        Whichever surface you start in, <Link href="/docs/goals">goals</Link>,{" "}
        <Link href="/docs/fusion">Fusion</Link> and your{" "}
        <Link href="/docs/skills">memory and skills</Link> follow you — it&apos;s one agent,
        many windows.
      </div>
    </DocsShell>
  );
}
