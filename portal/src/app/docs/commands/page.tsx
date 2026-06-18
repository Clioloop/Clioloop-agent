import type { Metadata } from "next";
import Link from "next/link";
import DocsShell from "@/components/DocsShell";

export const metadata: Metadata = {
  title: "Command reference — clio CLI & slash commands",
  description:
    "Every Clioloop command: clio subcommands for setup, surfaces and automation, plus in-session slash commands for goals, model switching, Agentic Fusion, Kanban, skills and more.",
  alternates: { canonical: "/docs/commands" },
};

export default function CommandsDoc() {
  return (
    <DocsShell
      current="commands"
      title="Command reference"
      description="All clio subcommands and in-session slash commands."
    >
      <div className="docs-breadcrumb">
        <Link href="/docs">Docs</Link> / Command reference
      </div>
      <h1>Command reference</h1>
      <p>
        <code>clio</code> on its own starts an interactive chat. Add a
        subcommand for everything else, or use slash commands mid-conversation.
        Run <code>/help</code> in any session to list exactly what your build
        supports.
      </p>

      <h2 id="cli">CLI subcommands</h2>
      <table>
        <thead>
          <tr>
            <th>Command</th>
            <th>What it does</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>
              <code>clio setup</code>
            </td>
            <td>
              First-run wizard — connect the Omni Loop Portal or add provider
              keys
            </td>
          </tr>
          <tr>
            <td>
              <code>clio auth</code>
            </td>
            <td>Log in / add providers</td>
          </tr>
          <tr>
            <td>
              <code>clio model</code>
            </td>
            <td>Pick model &amp; provider</td>
          </tr>
          <tr>
            <td>
              <code>clio status</code>
            </td>
            <td>Keys, model and health</td>
          </tr>
          <tr>
            <td>
              <code>clio doctor</code>
            </td>
            <td>Diagnose setup problems</td>
          </tr>
          <tr>
            <td>
              <code>clio update</code>
            </td>
            <td>Upgrade Clioloop</td>
          </tr>
          <tr>
            <td>
              <code>clio --tui</code>
            </td>
            <td>Full terminal UI</td>
          </tr>
          <tr>
            <td>
              <code>clio desktop</code>
            </td>
            <td>Desktop app</td>
          </tr>
          <tr>
            <td>
              <code>clio dashboard</code>
            </td>
            <td>Web dashboard</td>
          </tr>
          <tr>
            <td>
              <code>clio gateway</code>
            </td>
            <td>Messaging gateway (Telegram/Slack/WhatsApp/…)</td>
          </tr>
          <tr>
            <td>
              <code>clio send</code>
            </td>
            <td>Message a channel from a script</td>
          </tr>
          <tr>
            <td>
              <code>clio kanban</code>
            </td>
            <td>Multi-agent task board</td>
          </tr>
          <tr>
            <td>
              <code>clio cron</code>
            </td>
            <td>Scheduled jobs</td>
          </tr>
          <tr>
            <td>
              <code>clio skills</code>
            </td>
            <td>Manage skill packs</td>
          </tr>
          <tr>
            <td>
              <code>clio mcp</code>
            </td>
            <td>Connect MCP servers</td>
          </tr>
          <tr>
            <td>
              <code>clio memory</code>
            </td>
            <td>View / edit memory</td>
          </tr>
        </tbody>
      </table>

      <h2 id="slash">In-session slash commands</h2>
      <table>
        <thead>
          <tr>
            <th>Command</th>
            <th>What it does</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>
              <code>/help</code>
            </td>
            <td>List every command in your build</td>
          </tr>
          <tr>
            <td>
              <code>/goal</code>
            </td>
            <td>Keep working until a goal is judged done</td>
          </tr>
          <tr>
            <td>
              <code>/subgoal</code>
            </td>
            <td>Add acceptance criteria to the active goal</td>
          </tr>
          <tr>
            <td>
              <code>/model</code>
            </td>
            <td>Switch model or provider without restarting</td>
          </tr>
          <tr>
            <td>
              <code>/fusion</code>
            </td>
            <td>
              Agentic Fusion — planners + reviewers + your model (Pro+); use
              from a fresh session
            </td>
          </tr>
          <tr>
            <td>
              <code>/kanban</code>
            </td>
            <td>Open the task board</td>
          </tr>
          <tr>
            <td>
              <code>/skills</code>
            </td>
            <td>Load expertise for the task at hand</td>
          </tr>
          <tr>
            <td>
              <code>/tools</code>
            </td>
            <td>Enable / disable tools for the session</td>
          </tr>
          <tr>
            <td>
              <code>/curator</code> · <code>/evolve</code>
            </td>
            <td>Maintain and merge skills</td>
          </tr>
          <tr>
            <td>
              <code>/compress</code>
            </td>
            <td>Shrink context while keeping recent turns</td>
          </tr>
          <tr>
            <td>
              <code>/steer</code> · <code>/queue</code> ·{" "}
              <code>/background</code>
            </td>
            <td>Nudge, queue or background a prompt</td>
          </tr>
          <tr>
            <td>
              <code>/usage</code> · <code>/status</code>
            </td>
            <td>Token usage, limits and session info</td>
          </tr>
        </tbody>
      </table>

      <div className="callout">
        New here? Start with{" "}
        <Link href="/docs/getting-started">Getting started</Link>, then turn on{" "}
        <Link href="/docs/fusion">Agentic Fusion</Link>.
      </div>

      <div className="callout">
        <strong>Fusion session rule:</strong> use <code>/new</code> or{" "}
        <code>/reset</code> before a Fusion run and again after the final fused
        answer. This keeps planners and reviewers on clean context and avoids
        wasting managed usage.
      </div>
    </DocsShell>
  );
}
