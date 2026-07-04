import type { Dictionary } from "@/i18n/dictionaries/en";

export default function HowItWorks({ t }: { t: Dictionary["landing"]["how"] }) {
  return (
    <section className="section" data-reveal>
      <div className="section-head">
        <span className="eyebrow">{t.eyebrow}</span>
        <h2>
          {t.h2Lead} <span className="display-italic">{t.h2Italic}</span>
        </h2>
        <p>{t.lede}</p>
      </div>
      <div className="steps">
        {t.steps.map((step) => (
          <div className="step" key={step.title}>
            <h3>{step.title}</h3>
            <p>{step.body}</p>
            <code>{step.code}</code>
          </div>
        ))}
      </div>
    </section>
  );
}
