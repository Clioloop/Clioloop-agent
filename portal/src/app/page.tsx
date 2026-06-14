import Link from "next/link";
import IntroOverlay from "@/components/IntroOverlay";

export default function LandingPage() {
  return (
    <div className="page">
      <IntroOverlay />
      <div className="container">
        {/* ─── Hero ─────────────────────────────────────────────────── */}
        <section className="hero fade-up">
          <span className="hero-badge">∞ open source agent · one subscription</span>
          <h1>
            Every model.
            <br />
            Every tool.
            <br />
            <span className="gradient-text">One login.</span>
          </h1>
          <p className="lede">
            The Omni Loop Portal is the subscription gateway for the Clioloop agent:
            300+ frontier models plus web search, image generation, text-to-speech and
            a cloud browser — routed through one OAuth login. No API keys. Not for
            anything else: built strictly for your agent.
          </p>
          <div className="hero-actions">
            <a
              className="btn btn-primary btn-lg"
              href="https://github.com/Clioloop/Clioloop-agent/releases/latest/download/Clioloop-Setup.exe"
            >
              ⬇ Download for Windows
            </a>
            <Link href="#download" className="btn btn-ghost btn-lg">
              Install on Linux / macOS
            </Link>
            <Link href="/signup" className="btn btn-ghost btn-lg">
              Start free
            </Link>
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
                <span className="t-prompt">$</span> curl -fsSL{" "}
                https://raw.githubusercontent.com/Clioloop/Clioloop-agent/main/scripts/install.sh | bash
              </div>
              <div>
                <span className="t-green">✓</span> Clioloop installed{" "}
                <span className="t-dim">(or grab the Windows installer above)</span>
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
              <span className="s-label">Web search</span>
              <span className="s-value">Firecrawl</span>
            </div>
            <div>
              <span className="s-label">Image gen</span>
              <span className="s-value">FLUX</span>
            </div>
            <div>
              <span className="s-label">Premium TTS</span>
              <span className="s-value">Supertonic</span>
            </div>
            <div>
              <span className="s-label">Cloud browser</span>
              <span className="s-value">Included</span>
            </div>
          </div>
        </section>

        {/* ─── What is Clioloop ─────────────────────────────────────── */}
        <section className="section" id="what-is-clioloop">
          <div className="section-head">
            <span className="eyebrow">what is clioloop</span>
            <h2>The autonomous agent that grows with you</h2>
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
              <div className="card-icon">📦</div>
              <h3>Skills it can evolve</h3>
              <p>
                Reusable expertise packs load per task. Clioloop can even refine and merge
                them with <code>/evolve</code>, growing a library tuned to how you work.
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
                <Link href="/docs">Read the full setup guide →</Link>
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
                The same account powers <code>clio</code>, <code>clio --tui</code>, the
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
            <span className="c-cmd">/evolve</span>{" "}
            <span className="c-comment"># let Clioloop refine its own skill library</span>
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
              Start free with a free model and web search, or go Pro for many more
              models and the full Tool Gateway. Cancel anytime.
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
