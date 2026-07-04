import type { Dictionary } from "@/i18n/dictionaries/en";
import { PLANS, PLAN_ORDER, type PlanId } from "@/lib/plans";
import PlanButton from "@/components/PlanButton";
import { SITE_URL } from "@/lib/site";
import Reveal from "./Reveal";

// Dictionary-driven pricing page body, shared by /pricing and
// /{locale}/pricing. FAQ + Product structured data are built from the same
// dictionary so localized pages emit localized JSON-LD.
export default function PricingSections({ t }: { t: Dictionary["pricing"] }) {
  const faqJsonld = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: t.faq.map((f) => ({
      "@type": "Question",
      name: f.q,
      acceptedAnswer: { "@type": "Answer", text: f.a },
    })),
  };
  const productJsonld = {
    "@context": "https://schema.org",
    "@type": "Product",
    name: "Clioloop",
    description: t.lede,
    brand: { "@type": "Brand", name: "Clioloop" },
    offers: {
      "@type": "AggregateOffer",
      priceCurrency: "EUR",
      lowPrice: "0",
      highPrice: "250",
      offerCount: PLAN_ORDER.length,
      offers: PLAN_ORDER.map((id) => ({
        "@type": "Offer",
        name: PLANS[id].name,
        price: String(PLANS[id].priceEur),
        priceCurrency: "EUR",
        url: `${SITE_URL}/pricing`,
      })),
    },
  };

  return (
    <div className="page">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonld) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(productJsonld) }}
      />
      <div className="container">
        <Reveal>
          <div className="section-head fade-up" style={{ marginTop: 24 }}>
            <span className="eyebrow">{t.eyebrow}</span>
            <h2>
              {t.h2Lead} <span className="display-italic">{t.h2Italic}</span>
            </h2>
            <p>{t.lede}</p>
          </div>

          <div className="pricing-grid fade-up">
            {PLAN_ORDER.map((id: PlanId) => {
              const plan = PLANS[id];
              const featured = id === "pro";
              const flag = t.flags[id as keyof typeof t.flags];
              return (
                <div key={id} className={`price-card ${featured ? "featured" : ""}`}>
                  {flag && <span className="plan-flag">{flag}</span>}
                  <h3>{plan.name}</h3>
                  <p className="plan-tagline">{t.taglines[id]}</p>
                  <div className="plan-price">
                    €{plan.priceEur}
                    <span> {t.perMonth}</span>
                  </div>
                  <ul>
                    {t.features[id].map((f) => (
                      <li
                        key={f.text}
                        className={
                          f.kind === "fusion"
                            ? "li-fusion"
                            : f.kind === "music"
                              ? "li-music"
                              : f.kind === "off"
                                ? "li-off"
                                : undefined
                        }
                      >
                        {f.text}
                      </li>
                    ))}
                  </ul>
                  <PlanButton
                    plan={id}
                    featured={featured}
                    label={id === "free" ? t.startFree : `${t.choose} ${plan.name}`}
                  />
                </div>
              );
            })}
          </div>

          <div className="section-head" style={{ marginTop: 72 }} data-reveal>
            <h2 style={{ fontSize: 28 }}>{t.faqTitle}</h2>
          </div>
          <div className="grid-2" data-reveal>
            {t.faq.map((f) => (
              <div className="card" key={f.q}>
                <h3>{f.q}</h3>
                <p>{f.a}</p>
              </div>
            ))}
          </div>
        </Reveal>
      </div>
    </div>
  );
}
