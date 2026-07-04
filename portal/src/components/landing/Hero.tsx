import Link from "next/link";
import type { Dictionary } from "@/i18n/dictionaries/en";
import { InfinityMark } from "@/components/chrome";
import EnsembleWaveform from "./EnsembleWaveform";

const WINDOWS_INSTALLER =
  "https://github.com/Clioloop/Clioloop-agent/releases/latest/download/Clioloop-Setup.exe";

export default function Hero({ t }: { t: Dictionary["landing"]["hero"] }) {
  return (
    <section className="hero fade-up">
      <div className="hero-split">
        <div>
          <span className="hero-badge">
            <InfinityMark className="logo-mark" /> {t.badge}
          </span>
          <h1>
            {t.h1Lead}
            <br />
            <span className="display-italic gradient-text">{t.h1Italic}</span>
          </h1>
          <p className="lede">{t.lede}</p>
          <div className="hero-actions">
            <a className="btn btn-primary btn-lg" href={WINDOWS_INSTALLER}>
              {t.ctaWindows}
            </a>
            <Link href="#music" className="btn btn-ghost btn-lg">
              {t.ctaMusic}
            </Link>
            <Link href="#download" className="btn btn-ghost btn-lg">
              {t.ctaInstall}
            </Link>
          </div>
        </div>

        <EnsembleWaveform
          label={t.ensembleLabel}
          sub={t.ensembleSub}
          legend={{
            planners: t.legendPlanners,
            model: t.legendModel,
            reviewers: t.legendReviewers,
            fused: t.legendFused,
          }}
        />
      </div>

      <div className="terminal">
        <div className="terminal-bar">
          <span />
          <span />
          <span />
          <span className="t-title">{t.terminalTitle}</span>
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
        {t.strip.map((cell) => (
          <div key={cell.label}>
            <span className="s-label">{cell.label}</span>
            <span className="s-value">{cell.value}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
