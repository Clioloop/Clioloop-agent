import type { Metadata } from "next";
import Link from "next/link";
import DocsShell from "@/components/DocsShell";

export const metadata: Metadata = {
  title: "Agentic Fusion — frontier intelligence on open models",
  description:
    "How Clioloop's Agentic Fusion works: planner models propose routes, your main model does the visible full-tool work, reviewer models critique it, and everything fuses into one reviewed answer. Available on Pro and up.",
  alternates: { canonical: "/docs/fusion" },
};

export default function FusionDoc() {
  return (
    <DocsShell
      current="fusion"
      title="Agentic Fusion"
      description="Planner and reviewer models fuse one answer — frontier intelligence on open models."
    >
      <div className="docs-breadcrumb">
        <Link href="/docs">Docs</Link> / Agentic Fusion
      </div>
      <h1>Agentic Fusion</h1>
      <p>
        Agentic Fusion is Clioloop&apos;s way of producing{" "}
        <strong>frontier intelligence on open models</strong>. Instead of asking
        one model to do everything, Fusion surrounds your main model with a
        panel of helpers: planners propose routes, your model does the visible
        full-tool work, independent reviewers critique the draft, and it all
        fuses into one answer. The quality comes from the{" "}
        <strong>synthesis</strong> — not from running the same prompt five
        times.
      </p>

      <div className="callout">
        <strong>Plan requirement:</strong> Fusion is available on the{" "}
        <Link href="/pricing">Pro plan and up</Link> through the Omni Loop
        Portal. Run <code>/fusion status</code> to see your current
        configuration.
      </div>

      <div className="callout">
        <strong>Fresh-session rule:</strong> start a new session before every
        Fusion run, then reset again after the final fused answer is delivered.
        Use <code>/new</code> or <code>/reset</code> in CLI, TUI, Telegram and
        gateway sessions, or the desktop app&apos;s New Chat action. Fusion
        planners and reviewers work best with clean context; stale sessions can
        confuse them and waste managed usage.
      </div>

      <h2 id="why">Why fuse models?</h2>
      <p>
        A single cheap or open-weight model has blind spots. Fusion turns those
        blind spots into a strength by giving each model a role and a
        perspective:
      </p>
      <ul>
        <li>
          <strong>Diversity</strong> — planners reason from different angles
          (architect, implementer, researcher, critic, creative).
        </li>
        <li>
          <strong>Scaffolding</strong> — planners produce a concrete route; your
          model executes it with full tools; reviewers give actionable feedback.
        </li>
        <li>
          <strong>Synthesis over voting</strong> — a judge resolves
          contradictions instead of averaging, then a final pass integrates the
          consensus.
        </li>
        <li>
          <strong>Cost</strong> — a panel of open models can rival a frontier
          model for a fraction of the price per turn.
        </li>
      </ul>

      <h2 id="pipeline">The pipeline</h2>
      <p>
        Fusion runs four stages around a single user request. The planning,
        review, judge and synthesis stages run{" "}
        <strong>server-side on the Omni Loop Portal</strong> — only the working
        stage runs on your machine, where your model uses your real tools.
      </p>
      <ol>
        <li>
          <strong>Planning</strong> — 1–5 planner models analyse the request in
          parallel on the portal and output a structured plan: an ordered route
          of tool steps, concrete code blocks, risks and open questions.
        </li>
        <li>
          <strong>Working</strong> — your current chat model receives those
          plans and does the real work with the full toolset (files, shell,
          browser, image generation, and more). This stage runs on your machine
          and is fully visible — you watch the tool calls stream.
        </li>
        <li>
          <strong>Review</strong> — 1–5 reviewer models critique the draft from
          distinct angles (correctness, completeness, clarity, safety,
          delivery). Each returns a verdict — <code>APPROVE</code>,{" "}
          <code>REQUEST_CHANGES</code> or <code>REJECT</code> — with a score and
          exact fixes. If the judge asks for tool-bearing changes, one revision
          pass runs on your machine.
        </li>
        <li>
          <strong>Synthesis</strong> — the agent applies every mandatory change,
          resolves contradictions, integrates unique insights and delivers one
          clean final answer. It never mentions the panel — you just get the
          result.
        </li>
      </ol>

      <div className="code-block">
        planners ─┐ ├─▶ your main model ─▶ reviewers ─▶ one fused answer
        (read-only) (full tools, (read-only, (synthesised, visible) can see
        images) reviewed)
      </div>

      <h2 id="enable">Turn it on</h2>
      <p>
        In any Clioloop surface, run <code>/fusion</code> for an interactive
        picker, or configure it directly:
      </p>
      <div className="code-block">
        <span className="c-cmd">/fusion</span>{" "}
        <span className="c-comment">
          # interactive: choose advisors, reviewers, mode
        </span>
        <br />
        <span className="c-cmd">/fusion status</span>{" "}
        <span className="c-comment"># show the current config</span>
        <br />
        <span className="c-cmd">/fusion off</span>{" "}
        <span className="c-comment"># disable</span>
        <br />
        <br />
        <span className="c-comment">
          # pick models explicitly (1–5 of each)
        </span>
        <br />
        <span className="c-cmd">
          /fusion auto advisors=openai/gpt-oss-120b,qwen/qwen3-235b
          reviewers=deepseek/deepseek-v3.2,anthropic/claude-haiku-4.5
        </span>
      </div>
      <p>
        Modes: <code>auto</code> gates out trivial requests, <code>fast</code>{" "}
        uses just the first advisor and reviewer, and <code>full</code> runs the
        whole panel.
      </p>

      <h2 id="session-hygiene">Session hygiene</h2>
      <p>
        Treat each Fusion run as a clean-room collaboration. Begin from a fresh
        conversation so planners see only the current task, and reset after the
        final answer before starting another Fusion job. Clioloop shows a
        persistent reminder after successful Fusion runs, but it does not
        auto-reset your session because you may still want to read or save the
        final response.
      </p>
      <div className="code-block">
        <span className="c-cmd">/new</span>{" "}
        <span className="c-comment">
          # or /reset before starting the Fusion task
        </span>
        <br />
        <span className="c-cmd">/fusion</span>{" "}
        <span className="c-comment">
          # run the picker or use your saved config
        </span>
        <br />
        <span className="c-comment">
          # after the final answer arrives, reset again
        </span>
        <br />
        <span className="c-cmd">/reset</span>
      </div>

      <h2 id="config">Persisting a config</h2>
      <p>
        Fusion settings live in <code>~/.clio/config.local.yaml</code> so they
        apply to every session:
      </p>
      <div className="code-block">
        fusion:
        <br />
        {"  "}enabled: true
        <br />
        {"  "}mode: auto
        <br />
        {"  "}advisors:
        <br />
        {"    "}- openai/gpt-oss-120b
        <br />
        {"    "}- qwen/qwen3-235b
        <br />
        {"  "}reviewers:
        <br />
        {"    "}- deepseek/deepseek-v3.2
        <br />
        {"    "}- anthropic/claude-haiku-4.5
        <br />
        {"  "}judge: &quot;&quot;{"        "}
        <span className="c-comment"># empty = use the current chat model</span>
        <br />
        {"  "}synthesizer: &quot;&quot;
        <br />
        {"  "}max_total_tokens: 200000
      </div>

      <h2 id="safety">Safe by construction</h2>
      <p>
        Planners and reviewers are read-only <em>at the schema level</em> — the
        write, shell and browser tools are not even in their toolset, so they
        can research and critique but can never touch your files or run
        commands. Only your main model acts, and you can watch it. See{" "}
        <Link href="/docs/security">Security &amp; tokens</Link> for more.
      </p>

      <div className="callout">
        <strong>Try it:</strong> enable Fusion, then give Clioloop a meaty task
        like &quot;design and build a Python web scraper with tests.&quot; Watch
        the planning, working, review and synthesis phases stream by, then check{" "}
        <code>/fusion status</code> for the quality score of the run.
      </div>
    </DocsShell>
  );
}
