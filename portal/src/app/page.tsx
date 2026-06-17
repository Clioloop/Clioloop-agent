import Link from "next/link";
import type { Metadata } from "next";
import IntroOverlay from "@/components/IntroOverlay";
import { InfinityMark } from "@/components/chrome";

export const metadata: Metadata = {
  title: "Clioloop — Agentic Fusion: frontier intelligence on open models",
  description:
    "Clioloop is a self-improving AI assistant with Agentic Fusion — planner and reviewer models fuse one answer, creating frontier intelligence on open models. 300+ models and a full tool gateway through one login. No API keys.",
  alternates: { canonical: "/" },
};

// SoftwareApplication structured data lives on the home page so the product,
// its rating-free offers and the Agentic Fusion feature are indexable.
const APP_JSONLD = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "Clioloop",
  alternateName: "Omni Loop",
  applicationCategory: "DeveloperApplication",
  operatingSystem: "macOS, Linux, Windows",
  description:
    "A self-improving AI assistant and agent with Agentic Fusion — multiple open models plan, work and review to produce frontier intelligence. 300+ models plus web search, image generation, text-to-speech and a cloud browser through one login.",
  url: "https://portal.clioloop.com",
  offers: [
    { "@type": "Offer", name: "Free", price: "0", priceCurrency: "EUR" },
    { "@type": "Offer", name: "Pro", price: "20", priceCurrency: "EUR" },
    { "@type": "Offer", name: "Max", price: "100", priceCurrency: "EUR" },
    { "@type": "Offer", name: "Max 10x", price: "250", priceCurrency: "EUR" },
  ],
  featureList: [
    "Agentic Fusion — planner and reviewer models fuse one answer",
    "300+ frontier and open models through one login",
    "Standing goals and autonomous loops",
    "Multi-agent Kanban",
    "Memory and self-learning skills",
    "Tool gateway: web search, image generation, TTS, cloud browser",
  ],
};

export default function LandingPage() {
  return (
    <div className="page">
      <IntroOverlay />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(APP_JSONLD) }}
      />
      <div className="container">
        {/* ─── Hero ─────────────────────────────────────────────────── */}
        <section className="hero fade-up">
          <div className="hero-split">
            <div>
              <span className="hero-badge">
                <InfinityMark className="logo-mark" /> agentic fusion · 300+ models · one login
              </span>
              <h1>
                Frontier intelligence,
                <br />
                <span className="spectrum-text">fused</span> from open models.
              </h1>
              <p className="lede">
                Clioloop is the self-improving AI assistant with{" "}
                <strong>Agentic Fusion</strong>: a panel of models plans the route, your
                main model does the real work, independent reviewers critique it, and it
                all fuses into one answer you can trust. One login unlocks 300+ models and
                the full tool gateway — no API keys.
              </p>
              <div className="hero-actions">
                <a
                  className="btn btn-primary btn-lg"
                  href="https://github.com/Clioloop/Clioloop-agent/releases/latest/download/Clioloop-Setup.exe"
                >
                  ⬇ Download for Windows
                </a>
                <Link href="#fusion" className="btn btn-ghost btn-lg">
                  ✦ See Fusion
                </Link>
                <Link href="#download" className="btn btn-ghost btn-lg">
                  Install on Linux / macOS
                </Link>
              </div>
            </div>

            {/* Signature: spectral model-streams converging into one core. */}
            <div className="convergence" aria-hidden>
              <div className="cv-grid">
                <div className="cv-streams">
                  <span className="cv-stream s1">planner</span>
                  <span className="cv-stream s2">your model</span>
                  <span className="cv-stream s3">reviewer</span>
                  <span className="cv-stream s4">reviewer</span>
                </div>
                <div className="cv-rays">
                  <span className="cv-ray r1" />
                  <span className="cv-ray r2" />
                  <span className="cv-ray r3" />
                  <span className="cv-ray r4" />
                </div>
                <div className="cv-core">
                  <span>∞</span>
                </div>
              </div>
              <div className="cv-foot">
                <span>open models in</span>
                <span className="cv-answer">one fused answer</span>
              </div>
            </div>
          </div>

          <div className="terminal">
            <div className="terminal-bar">
              <span />
              <span />
              <span />
              <span className="t-title">install clioloop</span>
            </div>
            <div className="terminal-body">
              <div>
                <span className="t-dim"># macOS / Linux</span>
              </div>
              <div>
                <span className="t-prompt">$</span> curl -fsSL{" "}
                https://raw.githubusercontent.com/Clioloop/Clioloop-agent/main/scripts/install.sh | bash
              </div>
              <div>
                <span className="t-dim"># Windows (PowerShell)</span>
              </div>
              <div>
                <span className="t-prompt">PS&gt;</span> iex (irm{" "}
                https://raw.githubusercontent.com/Clioloop/Clioloop-agent/main/scripts/install.ps1)
              </div>
              <div>
                <span className="t-green">✓</span> Clioloop installed{" "}
                <span className="t-dim">(macOS · Linux · Windows)</span>
              </div>
              <div>&nbsp;</div>
              <div>
                <span className="t-prompt">$</span> clio setup{" "}
                <span className="t-dim"># choose Omni Loop Portal — one login, 300+ models</span>
              </div>
              <div className="t-dim">Opening browser… approve this device with code</div>
              <div>
                &nbsp;&nbsp;<span className="t-accent">WXYZ-2345</span>
              </div>
              <div>
                <span className="t-green">✓</span> Connected —{" "}
                <span className="t-green">Pro plan</span>,{" "}
                <span className="t-accent">anthropic/claude-sonnet-4.6</span>
              </div>
              <div>
                <span className="t-prompt">$</span> clio{" "}
                <span className="t-dim"># start looping ∞</span>
              </div>
            </div>
          </div>

          {/* What the subscription covers, at a glance */}
          <div className="services-strip">
            <div>
              <span className="s-label">Models</span>
              <span className="s-value">300+</span>
            </div>
            <div>
              <span className="s-label">Agentic Fusion</span>
              <span className="s-value">Pro & up</span>
            </div>
            <div>
              <span className="s-label">Web search</span>
              <span className="s-value">Included</span>
            </div>
            <div>
              <span className="s-label">Image gen</span>
              <span className="s-value">Fast</span>
            </div>
            <div>
              <span className="s-label">Premium TTS</span>
              <span className="s-value">Studio-grade</span>
            </div>
            <div>
              <span className="s-label">Cloud browser</span>
              <span className="s-value">Included</span>
            </div>
          </div>
        </section>

        {/* ─── Agentic Fusion (flagship) ────────────────────────────── */}
        <section className="section" id="fusion">
          <div className="section-head">
            <span className="eyebrow">✦ the flagship · pro plan and up</span>
            <h2>
              Agentic <span className="spectrum-text">Fusion</span> — frontier
              intelligence on open models
            </h2>
            <p>
              Run <code>/fusion</code> and put a whole crew of models on a single task.
              Planners propose routes, your main model does the real, full-tool work
              <strong> in the open</strong>, independent reviewers critique the draft, and
              everything fuses into one reviewed-and-approved answer. The quality comes from
              the <strong>synthesis</strong> — not from brute-forcing the same job five
              times — so cheap open models combine into something that rivals a frontier
              model, at a fraction of the cost.
            </p>
          </div>

          {/* Pipeline diagram (pure CSS): planners → main model → reviewers → fused. */}
          <div className="fusion-flagship">
            <div className="fusion-stage">
              <div className="fusion-tier">
                <span className="fusion-tier-label">1 · planners — read-only, in parallel</span>
                <div className="fusion-chips">
                  <span className="fusion-chip c1">advisor</span>
                  <span className="fusion-chip c1">advisor</span>
                  <span className="fusion-chip c1">advisor</span>
                  <span className="fusion-chip c1">+ up to 5</span>
                </div>
              </div>

              <div className="fusion-flow">routes ↓</div>

              <div className="fusion-core">
                <span className="fusion-core-label">your main model</span>
                <span className="fusion-core-sub">full-tool work · visible</span>
              </div>

              <div className="fusion-flow">draft ↓</div>

              <div className="fusion-tier">
                <span className="fusion-tier-label">2 · reviewers — read-only, can see images</span>
                <div className="fusion-chips">
                  <span className="fusion-chip c4">reviewer</span>
                  <span className="fusion-chip c4">reviewer</span>
                  <span className="fusion-chip c4">reviewer</span>
                  <span className="fusion-chip c4">+ up to 5</span>
                </div>
              </div>

              <div className="fusion-flow">↺ revise · approve ↓</div>

              <div className="fusion-final">one fused answer</div>
            </div>

            <div className="fusion-points">
              <div className="fusion-point">
                <h4>🛡️ Safe by construction</h4>
                <p>
                  Planners and reviewers are read-only at the schema level — they can research
                  and critique, but they can never touch your files or run commands.
                </p>
              </div>
              <div className="fusion-point">
                <h4>👁️ Work you can watch</h4>
                <p>
                  Your main model does the work live, not in a black box. Reviewers even get
                  <code> vision_analyze</code> so they can see the images it generates.
                </p>
              </div>
              <div className="fusion-point">
                <h4>✓ Reviewed before you see it</h4>
                <p>
                  A verdict loop revises the draft until reviewers approve — so the answer that
                  reaches you has already passed review.
                </p>
              </div>
              <div className="fusion-point">
                <h4>🧩 Any model combo</h4>
                <p>
                  Mix open-weight, OpenRouter and managed models as planners, reviewers and the
                  main worker. Pick them in a quick picker in any client. Pro plan and up.
                </p>
              </div>
            </div>
          </div>
          <div className="hero-actions" style={{ marginTop: 28 }}>
            <Link href="/docs/fusion" className="btn btn-ghost btn-lg">
              How Agentic Fusion works →
            </Link>
          </div>
        </section>

        {/* ─── What is Clioloop ─────────────────────────────────────── */}
        <section className="section" id="what-is-clioloop">
          <div className="section-head">
            <span className="eyebrow">what is clioloop</span>
            <h2>The autonomous AI assistant that grows with you</h2>
            <p>
              Clioloop is an open-source AI agent that lives in your terminal, a desktop
              app, a web dashboard and your chat apps. Give it a goal and it keeps
              working — planning, running tools, checking its own progress — until the
              job is done. It remembers what it learns about you and your work, and gets
              more capable the more you use it.
            </p>
          </div>
          <div className="grid-3">
            <div className="card">
              <div className="card-icon">🎯</div>
              <h3>Standing goals</h3>
              <p>
                <code>/goal</code> starts a loop: after every turn a judge decides if the
                goal is met. If not, Clioloop takes the next step automatically — across
                the terminal, gateway chats and the desktop app, with a live banner
                showing progress.
              </p>
            </div>
            <div className="card">
              <div className="card-icon">🗂️</div>
              <h3>Multi-agent Kanban</h3>
              <p>
                Break big work into a board of tasks. New tasks land in Triage for
                review, then worker agents pick them up, run them and report back —
                visible in both the web dashboard and the desktop app.
              </p>
            </div>
            <div className="card">
              <div className="card-icon">🧠</div>
              <h3>Memory &amp; self-learning</h3>
              <p>
                Clioloop keeps a persistent <code>MEMORY.md</code> and <code>USER.md</code>,
                updated automatically as it learns your preferences and projects — so the
                next session already knows you.
              </p>
            </div>
            <div className="card">
              <div className="card-icon">🔮</div>
              <h3>Agentic Fusion</h3>
              <p>
                <code>/fusion</code> puts a whole team of models on one task: up to five
                planners propose routes, your main model does the full-tool work in the open,
                up to five reviewers critique the draft, and it all fuses into one
                approved answer. Frontier intelligence on open models — Pro plan and up.
              </p>
            </div>
            <div className="card">
              <div className="card-icon">💬</div>
              <h3>Drive it from anywhere</h3>
              <p>
                A messaging gateway lets you run the agent from Telegram, Slack, WhatsApp,
                Discord and more — the same session, the same memory, on your phone.
              </p>
            </div>
            <div className="card">
              <div className="card-icon">🔌</div>
              <h3>Tools &amp; MCP</h3>
              <p>
                File editing, shell, web search &amp; extract, a cloud browser, image and
                video generation, text-to-speech — plus any MCP server you connect.
                Scheduled jobs run it on a <code>cron</code>.
              </p>
            </div>
          </div>
          <div className="hero-actions" style={{ marginTop: 28 }}>
            <Link href="/docs" className="btn btn-ghost btn-lg">
              Read the docs &amp; tutorials →
            </Link>
          </div>
        </section>

        {/* ─── Get Clioloop ─────────────────────────────────────────── */}
        <section className="section" id="download">
          <div className="section-head">
            <span className="eyebrow">get clioloop</span>
            <h2>Install in one line — or one click</h2>
            <p>
              Clioloop runs on Linux, macOS and Windows. It&apos;s fully open source —
              read every line on{" "}
              <a href="https://github.com/Clioloop/Clioloop-agent">GitHub</a>.
            </p>
          </div>
          <div className="grid-3">
            <div className="card">
              <div className="card-icon">🐧</div>
              <h3>Linux &amp; macOS</h3>
              <p>One command installs the CLI, TUI and desktop app:</p>
              <div className="code-block">
                <span className="c-cmd">
                  curl -fsSL
                  https://raw.githubusercontent.com/Clioloop/Clioloop-agent/main/scripts/install.sh
                  | bash
                </span>
              </div>
              <p style={{ marginTop: 14 }}>
                Then run <code>clio setup</code> and pick a model.
              </p>
            </div>
            <div className="card">
              <div className="card-icon">🪟</div>
              <h3>Windows</h3>
              <p>Download the installer and run it:</p>
              <a
                className="btn btn-primary btn-block"
                href="https://github.com/Clioloop/Clioloop-agent/releases/latest/download/Clioloop-Setup.exe"
              >
                ⬇ Download for Windows
              </a>
              <p style={{ marginTop: 14 }}>Or install from PowerShell:</p>
              <div className="code-block">
                <span className="c-cmd">
                  iex (irm
                  https://raw.githubusercontent.com/Clioloop/Clioloop-agent/main/scripts/install.ps1)
                </span>
              </div>
              <p className="t-dim" style={{ marginTop: 14, fontSize: "0.85rem" }}>
                <strong>Heads up:</strong> the installer isn&apos;t code-signed yet, so
                Windows SmartScreen may show a &quot;Windows protected your PC&quot;
                warning. That&apos;s expected — nothing harmful is in the app. Click{" "}
                <strong>More info → Run anyway</strong>. Everything is open source and
                auditable on{" "}
                <a href="https://github.com/Clioloop/Clioloop-agent">GitHub</a> if
                you&apos;d like to check first.
              </p>
            </div>
            <div className="card">
              <div className="card-icon">∞</div>
              <h3>Then connect</h3>
              <p>
                Run the setup wizard and choose <strong>Omni Loop Portal</strong> for one
                login and 300+ models — or bring your own provider keys.
              </p>
              <div className="code-block">
                <span className="c-cmd">clio setup</span>
              </div>
              <p style={{ marginTop: 14 }}>
                <Link href="/docs/getting-started">Read the full setup guide →</Link>
              </p>
            </div>
          </div>
        </section>

        {/* ─── Features ─────────────────────────────────────────────── */}
        <section className="section" id="features">
          <div className="section-head">
            <span className="eyebrow">why a portal</span>
            <h2>Built for autonomous loops</h2>
            <p>
              Clioloop doesn&apos;t stop until the goal is reached — your model and tool
              access shouldn&apos;t either.
            </p>
          </div>
          <div className="grid-3">
            <div className="card">
              <div className="card-icon">🔐</div>
              <h3>One-click OAuth setup</h3>
              <p>
                No keys to copy, ever. The CLI, TUI, desktop app and dashboard all
                connect with a browser approval — a device-code flow straight out of
                RFC 8628.
              </p>
            </div>
            <div className="card">
              <div className="card-icon">🧠</div>
              <h3>300+ models, one endpoint</h3>
              <p>
                Claude, GPT, Gemini, Grok, DeepSeek, Qwen, Kimi and every notable open
                model — switch mid-session with <code>/model</code>.
              </p>
            </div>
            <div className="card">
              <div className="card-icon">🧰</div>
              <h3>The Tool Gateway</h3>
              <p>
                Web search &amp; extract, image and video generation, text-to-speech and
                cloud browser sessions — all billed against your subscription instead of
                four separate vendor accounts.
              </p>
            </div>
            <div className="card">
              <div className="card-icon">⚡</div>
              <h3>Streaming-first proxy</h3>
              <p>
                Full OpenAI-compatible inference with SSE streaming, tool calls and
                vision — everything the agent loop needs at full speed.
              </p>
            </div>
            <div className="card">
              <div className="card-icon">🔄</div>
              <h3>Rotating, revocable tokens</h3>
              <p>
                Single-use refresh tokens with reuse detection. Lose a laptop? The
                whole device family is revoked the moment the old token is replayed.
              </p>
            </div>
            <div className="card">
              <div className="card-icon">🖥️</div>
              <h3>Every surface</h3>
              <p>
                The same account powers <code>clio</code>, the terminal UI, the
                desktop app and the web dashboard. Connect once, loop anywhere.
              </p>
            </div>
          </div>
        </section>

        {/* ─── How it works ─────────────────────────────────────────── */}
        <section className="section">
          <div className="section-head">
            <span className="eyebrow">how it works</span>
            <h2>Connected in under a minute</h2>
            <p>The quick setup is the default path in every Clioloop surface.</p>
          </div>
          <div className="steps">
            <div className="step">
              <h3>Run the setup</h3>
              <p>
                Install Clioloop and run the wizard. &quot;Omni Loop Portal&quot; is the
                first option.
              </p>
              <code>clio setup</code>
            </div>
            <div className="step">
              <h3>Approve in the browser</h3>
              <p>
                Your browser opens this portal with a device code. Log in, check the
                code matches, click approve.
              </p>
              <code>WXYZ-2345 ✓</code>
            </div>
            <div className="step">
              <h3>Pick a model &amp; loop</h3>
              <p>
                Choose from the live catalog and start. Tokens refresh automatically —
                you never touch a key.
              </p>
              <code>clio</code>
            </div>
          </div>
        </section>

        {/* ─── Commands ─────────────────────────────────────────────── */}
        <section className="section" id="commands">
          <div className="section-head">
            <span className="eyebrow">commands</span>
            <h2>Everything Clioloop can do, from one CLI</h2>
            <p>
              <code>clio</code> on its own starts an interactive chat. Add a subcommand
              for everything else — or use slash commands mid-conversation.
            </p>
          </div>
          <div className="grid-3">
            <div className="card">
              <h3>Set up &amp; connect</h3>
              <ul className="cmd-list">
                <li><code>clio setup</code> — first-run wizard</li>
                <li><code>clio auth</code> — log in / add providers</li>
                <li><code>clio model</code> — pick model &amp; provider</li>
                <li><code>clio status</code> — keys, model, health</li>
                <li><code>clio doctor</code> — diagnose problems</li>
                <li><code>clio update</code> — upgrade Clioloop</li>
              </ul>
            </div>
            <div className="card">
              <h3>Run &amp; surfaces</h3>
              <ul className="cmd-list">
                <li><code>clio</code> — interactive chat</li>
                <li><code>clio --tui</code> — full terminal UI</li>
                <li><code>clio desktop</code> — desktop app</li>
                <li><code>clio dashboard</code> — web dashboard</li>
                <li><code>clio gateway</code> — Telegram/Slack/WhatsApp…</li>
                <li><code>clio send</code> — message a channel from scripts</li>
              </ul>
            </div>
            <div className="card">
              <h3>Work &amp; automate</h3>
              <ul className="cmd-list">
                <li><code>clio kanban</code> — multi-agent task board</li>
                <li><code>clio cron</code> — scheduled jobs</li>
                <li><code>clio skills</code> — manage skill packs</li>
                <li><code>clio mcp</code> — connect MCP servers</li>
                <li><code>clio memory</code> — view/edit memory</li>
                <li><code>clio sessions</code> · <code>clio profile</code></li>
              </ul>
            </div>
          </div>
          <div className="section-head" style={{ marginTop: 36 }}>
            <span className="eyebrow">in-session</span>
            <h3 style={{ fontSize: "1.4rem" }}>Slash commands, mid-conversation</h3>
          </div>
          <div className="code-block">
            <span className="c-cmd">/goal</span>{" "}
            <span className="c-comment"># keep working until a goal is judged done</span>
            <br />
            <span className="c-cmd">/subgoal</span>{" "}
            <span className="c-comment"># add acceptance criteria to the active goal</span>
            <br />
            <span className="c-cmd">/model</span>{" "}
            <span className="c-comment"># switch model or provider without restarting</span>
            <br />
            <span className="c-cmd">/kanban</span>{" "}
            <span className="c-comment"># open the task board</span>
            <br />
            <span className="c-cmd">/skills</span>{" "}
            <span className="c-comment"># load expertise for the task at hand</span>
            <br />
            <span className="c-cmd">/fusion</span>{" "}
            <span className="c-comment"># planners + reviewers + your model → one fused answer (Pro)</span>
            <br />
            <span className="c-cmd">/help</span>{" "}
            <span className="c-comment"># list every command in your build</span>
          </div>
        </section>

        {/* ─── CTA ──────────────────────────────────────────────────── */}
        <section className="section">
          <div className="cta-banner">
            <span className="eyebrow">∞ start looping</span>
            <h2 style={{ marginTop: 18 }}>Give your agent the whole universe</h2>
            <p>
              Start free with one model, or go Pro for the full 300+ catalog, the Tool
              Gateway and Agentic Fusion. Cancel anytime.
            </p>
            <div className="hero-actions">
              <Link href="/pricing" className="btn btn-primary btn-lg">
                See pricing
              </Link>
              <Link href="/docs" className="btn btn-ghost btn-lg">
                Browse the docs
              </Link>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
