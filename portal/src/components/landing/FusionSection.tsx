import Link from "next/link";
import type { Dictionary } from "@/i18n/dictionaries/en";

export default function FusionSection({ t }: { t: Dictionary["landing"]["fusion"] }) {
  return (
    <section className="section" id="fusion" data-reveal>
      <div className="section-head">
        <span className="eyebrow">{t.eyebrow}</span>
        <h2>
          {t.h2Lead} <span className="display-italic">{t.h2Italic}</span>
        </h2>
        <p>{t.lede}</p>
      </div>

      {/* Pipeline diagram (pure CSS): planners → main model → reviewers → fused. */}
      <div className="fusion-flagship">
        <div className="fusion-stage">
          <div className="fusion-tier">
            <span className="fusion-tier-label">{t.tierPlanners}</span>
            <div className="fusion-chips">
              <span className="fusion-chip c1">{t.chipAdvisor}</span>
              <span className="fusion-chip c1">{t.chipAdvisor}</span>
              <span className="fusion-chip c1">{t.chipAdvisor}</span>
              <span className="fusion-chip c1">{t.chipMore}</span>
            </div>
          </div>

          <div className="fusion-flow">{t.flowRoutes}</div>

          <div className="fusion-core">
            <span className="fusion-core-label">{t.coreLabel}</span>
            <span className="fusion-core-sub">{t.coreSub}</span>
          </div>

          <div className="fusion-flow">{t.flowDraft}</div>

          <div className="fusion-tier">
            <span className="fusion-tier-label">{t.tierReviewers}</span>
            <div className="fusion-chips">
              <span className="fusion-chip c4">{t.chipReviewer}</span>
              <span className="fusion-chip c4">{t.chipReviewer}</span>
              <span className="fusion-chip c4">{t.chipReviewer}</span>
              <span className="fusion-chip c4">{t.chipMore}</span>
            </div>
          </div>

          <div className="fusion-flow">{t.flowVerdict}</div>

          <div className="fusion-final">{t.final}</div>
        </div>

        <div className="fusion-points">
          {t.points.map((point) => (
            <div className="fusion-point" key={point.title}>
              <h4>
                {point.icon} {point.title}
              </h4>
              <p>{point.body}</p>
            </div>
          ))}
        </div>
      </div>
      <div className="hero-actions" style={{ marginTop: 28 }}>
        <Link href="/docs/research" className="btn btn-primary btn-lg">
          {t.ctaResearch}
        </Link>
        <Link href="/docs/fusion" className="btn btn-ghost btn-lg">
          {t.ctaHow}
        </Link>
      </div>
    </section>
  );
}
