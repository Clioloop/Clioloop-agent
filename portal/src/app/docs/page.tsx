import type { Metadata } from "next";
import Link from "next/link";
import DocsShell from "@/components/DocsShell";

export const metadata: Metadata = {
  title: "Docs & tutorials — Clioloop AI assistant",
  description:
    "Learn Clioloop: install and connect, run Agentic Fusion, set standing goals and autonomous loops, switch between 300+ models, use the tool gateway, drive every surface, and more.",
  alternates: { canonical: "/docs" },
};

const TILES: { slug: string; icon: string; title: string; blurb: string }[] = [
  { slug: "getting-started", icon: "🚀", title: "Getting started", blurb: "Install on macOS, Linux or Windows and connect with one browser approval." },
  { slug: "fusion", icon: "🔮", title: "Agentic Fusion", blurb: "How planners, your model and reviewers fuse one answer — frontier intelligence on open models." },
  { slug: "goals", icon: "🎯", title: "Goals & loops", blurb: "Set a standing goal and let Clioloop loop until a judge decides it's done." },
  { slug: "models", icon: "🧠", title: "Models & switching", blurb: "Pick from 300+ models, switch mid-session with /model, and bring your own providers." },
  { slug: "tools", icon: "🧰", title: "Tools & gateway", blurb: "File edits, shell, web search, image/video, TTS, cloud browser and MCP servers." },
  { slug: "surfaces", icon: "🖥️", title: "Surfaces", blurb: "CLI, terminal UI, desktop app, web dashboard and messaging gateways." },
  { slug: "kanban", icon: "🗂️", title: "Multi-agent Kanban", blurb: "Break work into a board and let worker agents pick up tasks and report back." },
  { slug: "skills", icon: "✨", title: "Skills & memory", blurb: "Persistent memory plus skills the agent generates, curates and evolves over time." },
  { slug: "security", icon: "🔐", title: "Security & tokens", blurb: "Device-code OAuth, rotating single-use tokens and read-only fusion panels." },
  { slug: "commands", icon: "⌨️", title: "Command reference", blurb: "Every clio subcommand and in-session slash command in one place." },
  { slug: "research", icon: "📊", title: "Research Paper", blurb: "Benchmark study: GLM 5.2 + Agentic Fusion matches Claude Fable 5 and exceeds Opus 4.8 and GPT-5.5." },
];

export default function DocsHub() {
  return (
    <DocsShell
      current=""
      title="Clioloop documentation"
      description="Install, connect and master Clioloop — the self-improving AI assistant with Agentic Fusion."
    >
      <h1>Clioloop documentation</h1>
      <p>
        Clioloop is a self-improving AI assistant that lives in your terminal, a desktop
        app, a web dashboard and your chat apps. Its flagship is{" "}
        <Link href="/docs/fusion">Agentic Fusion</Link> — a panel of models that plans,
        works and reviews to produce frontier intelligence on open models. These guides
        take you from install to advanced multi-agent workflows.
      </p>

      <h2 id="quickstart">Quick start</h2>
      <p>Install, connect, and start your first loop in under a minute:</p>
      <div className="code-block">
        <span className="c-comment"># 1 · install (macOS / Linux)</span>
        <br />
        <span className="c-cmd">curl -fsSL https://raw.githubusercontent.com/Clioloop/Clioloop-agent/main/scripts/install.sh | bash</span>
        <br />
        <br />
        <span className="c-comment"># 2 · connect to Omni Loop Portal (one login, 300+ models)</span>
        <br />
        <span className="c-cmd">clio setup</span>
        <br />
        <br />
        <span className="c-comment"># 3 · start chatting / looping</span>
        <br />
        <span className="c-cmd">clio</span>
      </div>
      <p>
        On Windows, download{" "}
        <a href="https://github.com/Clioloop/Clioloop-agent/releases/latest/download/Clioloop-Setup.exe">
          Clioloop-Setup.exe
        </a>{" "}
        and run it. Full walkthrough in{" "}
        <Link href="/docs/getting-started">Getting started</Link>.
      </p>

      <h2 id="guides">All guides</h2>
      <div className="grid-3" style={{ marginTop: 8 }}>
        {TILES.map((t) => (
          <Link key={t.slug} href={`/docs/${t.slug}`} className="card">
            <div className="card-icon">{t.icon}</div>
            <h3>{t.title}</h3>
            <p>{t.blurb}</p>
            <span className="card-more">Read →</span>
          </Link>
        ))}
      </div>
    </DocsShell>
  );
}
