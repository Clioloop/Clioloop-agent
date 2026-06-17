import type { Metadata } from "next";
import Link from "next/link";
import DocsShell from "@/components/DocsShell";

export const metadata: Metadata = {
  title: "Skills & memory — the self-improving agent",
  description:
    "Clioloop learns: it keeps persistent memory across sessions and generates reusable skills from repeated work, then curates and evolves them over time. This is what makes the agent self-improving.",
  alternates: { canonical: "/docs/skills" },
};

export default function SkillsDoc() {
  return (
    <DocsShell
      current="skills"
      title="Skills & memory"
      description="Persistent memory and self-generated skills make Clioloop improve with use."
    >
      <div className="docs-breadcrumb">
        <Link href="/docs">Docs</Link> / Skills &amp; memory
      </div>
      <h1>Skills &amp; memory</h1>
      <p>
        Clioloop is <strong>self-improving</strong>: it remembers what it learns about you
        and your work, and it turns repeated work into reusable skills that get better
        over time. The next session already knows you.
      </p>

      <h2 id="memory">Memory</h2>
      <p>
        Clioloop keeps a persistent <code>MEMORY.md</code> and <code>USER.md</code>,
        updated automatically as it learns your preferences and projects. Long-running
        context is summarised and deduplicated so sessions stay sharp.
      </p>
      <div className="code-block">
        <span className="c-cmd">clio memory</span>{" "}
        <span className="c-comment"># view or edit what the agent remembers</span>
        <br />
        <span className="c-cmd">/compress</span>{" "}
        <span className="c-comment"># shrink context while keeping recent turns</span>
      </div>

      <h2 id="skills">Skills</h2>
      <p>
        When the agent notices a repeated pattern of work, it can generate a reusable{" "}
        <strong>skill</strong> — packaged expertise it can load on demand for the task at
        hand. Skills improve during use and can be shared.
      </p>
      <div className="code-block">
        <span className="c-cmd">/skills</span>{" "}
        <span className="c-comment"># search, browse, inspect, install, audit</span>
        <br />
        <span className="c-cmd">clio skills</span>{" "}
        <span className="c-comment"># manage skill packs from a shell</span>
      </div>

      <h2 id="curate">Curate &amp; evolve</h2>
      <p>
        A background curator keeps the skill library healthy — archiving stale skills,
        merging overlapping ones and suggesting improvements:
      </p>
      <ul>
        <li><code>/curator status</code> — see what the curator is doing; pin/unpin or restore skills</li>
        <li><code>/evolve --dry-run</code> — preview merges and archives before applying</li>
      </ul>

      <div className="callout">
        Memory and skills travel with your account, so improvements show up across every{" "}
        <Link href="/docs/surfaces">surface</Link> — terminal, desktop, dashboard and chat.
      </div>
    </DocsShell>
  );
}
