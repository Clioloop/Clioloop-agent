import type { Metadata } from "next";
import Link from "next/link";
import DocsShell from "@/components/DocsShell";

export const metadata: Metadata = {
  title: "Multi-agent Kanban",
  description:
    "Break big work into a board of tasks and let Clioloop worker agents pick them up, run them and report back. New tasks land in Triage for review; progress is visible in the desktop app and web dashboard.",
  alternates: { canonical: "/docs/kanban" },
};

export default function KanbanDoc() {
  return (
    <DocsShell
      current="kanban"
      title="Multi-agent Kanban"
      description="A task board where worker agents pick up work and report back."
    >
      <div className="docs-breadcrumb">
        <Link href="/docs">Docs</Link> / Multi-agent Kanban
      </div>
      <h1>Multi-agent Kanban</h1>
      <p>
        For work too big for a single loop, Clioloop has a multi-agent Kanban board. You
        break the job into tasks; worker agents pick them up, run them and report back. New
        tasks land in <strong>Triage</strong> for review before they&apos;re worked, and
        progress is visible in both the desktop app and the web dashboard.
      </p>

      <h2 id="open">Open the board</h2>
      <div className="code-block">
        <span className="c-cmd">/kanban</span>{" "}
        <span className="c-comment"># open the board in any surface</span>
        <br />
        <span className="c-cmd">clio kanban</span>{" "}
        <span className="c-comment"># from a shell</span>
      </div>

      <h2 id="flow">How work flows</h2>
      <ul>
        <li><strong>Triage</strong> — new tasks wait here for you to approve or refine.</li>
        <li><strong>In progress</strong> — worker agents pick up approved tasks and execute them with the full toolset.</li>
        <li><strong>Done</strong> — completed tasks report results back to the board.</li>
      </ul>
      <p>
        Because each worker is a full Clioloop agent, tasks can use{" "}
        <Link href="/docs/tools">tools</Link>, switch <Link href="/docs/models">models</Link>{" "}
        and even run <Link href="/docs/fusion">Agentic Fusion</Link> on their own.
      </p>

      <div className="callout">
        Kanban pairs naturally with <Link href="/docs/goals">standing goals</Link>: a goal
        drives one continuous thread, while the board fans work out across parallel
        agents. On Max&nbsp;10x, run agent swarms for heavy throughput.
      </div>
    </DocsShell>
  );
}
