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
            <Link href="/signup" className="btn btn-primary btn-lg">
              Start free
            </Link>
            <Link href="/docs" className="btn btn-ghost btn-lg">
              Read the docs
            </Link>
          </div>

          <div className="terminal">
            <div className="terminal-bar">
              <span />
              <span />
              <span />
              <span className="t-title">clio setup</span>
            </div>
            <div className="terminal-body">
              <div>
                <span className="t-prompt">$</span> clio setup
              </div>
              <div className="t-dim">∞ Clioloop Setup — first run detected</div>
              <div>
                <span className="t-accent">❯ 1.</span> Omni Loop Portal{" "}
                <span className="t-dim">— one login, 300+ models (recommended)</span>
              </div>
              <div className="t-dim">&nbsp;&nbsp;2. Bring your own provider (OpenAI, Anthropic, …)</div>
              <div>&nbsp;</div>
              <div className="t-dim">Opening browser… approve this device with code</div>
              <div>
                &nbsp;&nbsp;<span className="t-accent">WXYZ-2345</span>
              </div>
              <div>
                <span className="t-green">✓</span> Connected to Omni Loop Portal —{" "}
                <span className="t-green">Pro plan</span>
              </div>
              <div>
                <span className="t-green">✓</span> Default model:{" "}
                <span className="t-accent">anthropic/claude-sonnet-4.6</span>
              </div>
              <div>
                <span className="t-green">✓</span> Tools enabled:{" "}
                <span className="t-dim">web search · image gen · tts · browser</span>
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

        {/* ─── CTA ──────────────────────────────────────────────────── */}
        <section className="section">
          <div className="cta-banner">
            <span className="eyebrow">∞ start looping</span>
            <h2 style={{ marginTop: 18 }}>Give your agent the whole universe</h2>
            <p>
              Start free with community models and web search, or go Pro for the
              frontier and the full Tool Gateway. Cancel anytime.
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
