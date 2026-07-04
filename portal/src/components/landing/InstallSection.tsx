import Link from "next/link";
import type { Dictionary } from "@/i18n/dictionaries/en";

const REPO = "https://github.com/Clioloop/Clioloop-agent";
const WINDOWS_INSTALLER = `${REPO}/releases/latest/download/Clioloop-Setup.exe`;

export default function InstallSection({ t }: { t: Dictionary["landing"]["install"] }) {
  return (
    <section className="section" id="download" data-reveal>
      <div className="section-head">
        <span className="eyebrow">{t.eyebrow}</span>
        <h2>
          {t.h2Lead} <span className="display-italic">{t.h2Italic}</span>
        </h2>
        <p>
          {t.lede} <a href={REPO}>GitHub</a>.
        </p>
      </div>
      <div className="grid-3">
        <div className="card">
          <div className="card-icon">🐧</div>
          <h3>{t.linuxTitle}</h3>
          <p>{t.linuxBody}</p>
          <div className="code-block">
            <span className="c-cmd">
              curl -fsSL https://raw.githubusercontent.com/Clioloop/Clioloop-agent/main/scripts/install.sh | bash
            </span>
          </div>
          <p style={{ marginTop: 14 }}>{t.linuxAfter}</p>
        </div>
        <div className="card">
          <div className="card-icon">🪟</div>
          <h3>{t.windowsTitle}</h3>
          <p>{t.windowsBody}</p>
          <a className="btn btn-primary btn-block" href={WINDOWS_INSTALLER}>
            {t.windowsCta}
          </a>
          <p style={{ marginTop: 14 }}>{t.windowsPs}</p>
          <div className="code-block">
            <span className="c-cmd">
              iex (irm https://raw.githubusercontent.com/Clioloop/Clioloop-agent/main/scripts/install.ps1)
            </span>
          </div>
          <p className="t-dim" style={{ marginTop: 14, fontSize: "0.85rem" }}>
            {t.windowsWarn}
          </p>
        </div>
        <div className="card">
          <div className="card-icon">∞</div>
          <h3>{t.connectTitle}</h3>
          <p>{t.connectBody}</p>
          <div className="code-block">
            <span className="c-cmd">clio setup</span>
          </div>
          <p style={{ marginTop: 14 }}>
            <Link href="/docs/getting-started">{t.connectAfter}</Link>
          </p>
        </div>
      </div>
    </section>
  );
}
