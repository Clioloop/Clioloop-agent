import Link from "next/link";
import type { Dictionary } from "@/i18n/dictionaries/en";
import { PLANS, PLAN_ORDER } from "@/lib/plans";

export default function PricingTeaser({
  t,
  pricingHref,
}: {
  t: Dictionary["landing"]["pricingTeaser"];
  pricingHref: string;
}) {
  return (
    <section className="section" id="plans" data-reveal>
      <div className="section-head">
        <span className="eyebrow">{t.eyebrow}</span>
        <h2>
          {t.h2Lead} <span className="display-italic">{t.h2Italic}</span>
        </h2>
        <p>{t.lede}</p>
      </div>
      <div className="pricing-grid">
        {PLAN_ORDER.map((id) => {
          const plan = PLANS[id];
          return (
            <div key={id} className={`price-card ${id === "pro" ? "featured" : ""}`}>
              <h3>{plan.name}</h3>
              <p className="plan-tagline">{t.taglines[id]}</p>
              <div className="plan-price">
                €{plan.priceEur}
                <span> {t.perMonth}</span>
              </div>
              <Link
                href={pricingHref}
                className={`btn btn-block ${id === "pro" ? "btn-primary" : "btn-ghost"}`}
              >
                {t.cta}
              </Link>
            </div>
          );
        })}
      </div>
    </section>
  );
}
