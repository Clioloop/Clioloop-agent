import type { Metadata } from "next";
import Link from "next/link";
import DocsShell from "@/components/DocsShell";

export const metadata: Metadata = {
  title: "Goals & autonomous loops",
  description:
    "Set a standing goal and Clioloop keeps working — planning, running tools and judging its own progress after every turn — until the goal is met. The autonomous loop at the heart of the agent.",
  alternates: { canonical: "/docs/goals" },
};

export default function GoalsDoc() {
  return (
    <DocsShell
      current="goals"
      title="Goals & autonomous loops"
      description="Set a goal and let Clioloop loop until a judge decides it's done."
    >
      <div className="docs-breadcrumb">
        <Link href="/docs">Docs</Link> / Goals &amp; loops
      </div>
      <h1>Goals &amp; autonomous loops</h1>
      <p>
        Clioloop is built to <strong>not stop until the goal is reached</strong>. A
        standing goal turns a single request into an autonomous loop: after every turn a
        judge checks whether the goal is met, and if not, the agent takes the next step
        on its own.
      </p>

      <h2 id="set">Set a goal</h2>
      <div className="code-block">
        <span className="c-cmd">/goal</span> ship a working REST API with tests and a README
      </div>
      <p>
        From there, each turn ends with a judgement. If the goal isn&apos;t satisfied,
        Clioloop continues automatically — across the terminal, the desktop app and
        gateway chats — with a live banner showing progress.
      </p>

      <h2 id="control">Control the loop</h2>
      <ul>
        <li><code>/goal status</code> — show the active goal and progress</li>
        <li><code>/goal pause</code> · <code>/goal resume</code> — hold or continue the loop</li>
        <li><code>/goal clear</code> — drop the standing goal</li>
        <li><code>/subgoal</code> — add acceptance criteria the judge must satisfy</li>
      </ul>

      <h2 id="criteria">Acceptance criteria</h2>
      <p>
        Subgoals make &quot;done&quot; concrete. Add the conditions that matter and the
        judge will hold the loop open until they&apos;re all met:
      </p>
      <div className="code-block">
        <span className="c-cmd">/subgoal</span> all tests pass
        <br />
        <span className="c-cmd">/subgoal</span> endpoints documented in the README
      </div>

      <h2 id="steer">Steer without stopping</h2>
      <p>While a loop runs you can nudge it without breaking flow:</p>
      <ul>
        <li><code>/steer</code> — inject a message after the next tool call</li>
        <li><code>/queue</code> (<code>/q</code>) — queue a prompt for the next turn</li>
        <li><code>/background</code> (<code>/bg</code>) — run a prompt in the background</li>
      </ul>

      <div className="callout">
        Pair goals with <Link href="/docs/fusion">Agentic Fusion</Link> for high-stakes
        work: the loop keeps going while a panel of models plans and reviews each draft.
        For parallel workstreams, hand tasks to the{" "}
        <Link href="/docs/kanban">multi-agent Kanban</Link> board instead.
      </div>
    </DocsShell>
  );
}
