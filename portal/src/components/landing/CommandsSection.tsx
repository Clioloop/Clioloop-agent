import type { Dictionary } from "@/i18n/dictionaries/en";

function CmdCard({ title, items }: { title: string; items: { cmd: string; desc: string }[] }) {
  return (
    <div className="card">
      <h3>{title}</h3>
      <ul className="cmd-list">
        {items.map((item) => (
          <li key={item.cmd}>
            <code>{item.cmd}</code> — {item.desc}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function CommandsSection({ t }: { t: Dictionary["landing"]["commands"] }) {
  return (
    <section className="section" id="commands" data-reveal>
      <div className="section-head">
        <span className="eyebrow">{t.eyebrow}</span>
        <h2>
          {t.h2Lead} <span className="display-italic">{t.h2Italic}</span>
        </h2>
        <p>{t.lede}</p>
      </div>
      <div className="grid-3">
        <CmdCard title={t.col1Title} items={t.col1} />
        <CmdCard title={t.col2Title} items={t.col2} />
        <CmdCard title={t.col3Title} items={t.col3} />
      </div>
      <div className="section-head" style={{ marginTop: 36 }}>
        <span className="eyebrow">{t.slashEyebrow}</span>
        <h3 style={{ fontSize: "1.4rem" }}>{t.slashTitle}</h3>
      </div>
      <div className="code-block">
        {t.slash.map((line, i) => (
          <span key={line.cmd}>
            {i > 0 && <br />}
            <span className="c-cmd">{line.cmd}</span>{" "}
            <span className="c-comment"># {line.desc}</span>
          </span>
        ))}
      </div>
    </section>
  );
}
