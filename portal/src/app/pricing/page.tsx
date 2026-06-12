import type { Metadata } from "next";
import { PLANS, PLAN_ORDER } from "@/lib/plans";
import PlanButton from "@/components/PlanButton";

export const metadata: Metadata = {
  title: "Pricing — Omni Loop Portal",
};

const FLAGS: Record<string, string | undefined> = {
  pro: "Most popular",
  max20x: "Best for fleets",
};

export default function PricingPage() {
  return (
    <div className="page">
      <div className="container">
        <div className="section-head fade-up" style={{ marginTop: 24 }}>
          <span className="eyebrow">pricing</span>
          <h2>Simple plans, serious usage</h2>
          <p>
            Every plan includes the full Omni Loop experience: one-click setup on CLI,
            TUI, desktop and dashboard, streaming inference, the Tool Gateway, usage
            metering and rotating device tokens. No API keys — your subscription is
            the credential.
          </p>
        </div>

        <div className="pricing-grid fade-up">
          {PLAN_ORDER.map((id) => {
            const plan = PLANS[id];
            const featured = id === "pro";
            return (
              <div key={id} className={`price-card ${featured ? "featured" : ""}`}>
                {FLAGS[id] && <span className="plan-flag">{FLAGS[id]}</span>}
                <h3>{plan.name}</h3>
                <p className="plan-tagline">{plan.tagline}</p>
                <div className="plan-price">
                  €{plan.priceEur}
                  <span> /month</span>
                </div>
                <ul>
                  {plan.features.map((f) => (
                    <li key={f}>{f}</li>
                  ))}
                </ul>
                <PlanButton
                  plan={id}
                  featured={featured}
                  label={id === "free" ? "Start free" : `Choose ${plan.name}`}
                />
              </div>
            );
          })}
        </div>

        <div className="section-head" style={{ marginTop: 72 }}>
          <h2 style={{ fontSize: 24 }}>Pricing questions</h2>
        </div>
        <div className="grid-3">
          <div className="card">
            <h3>Why does Free need a card?</h3>
            <p>
              A one-time card verification keeps bots and abuse off the free models. You
              are never charged on the Free plan — verification is a €0 authorization.
            </p>
          </div>
          <div className="card">
            <h3>What does &quot;usage&quot; mean?</h3>
            <p>
              Each request is metered at the upstream model&apos;s real cost. Your plan
              includes a monthly allowance; the dashboard shows live consumption per
              month and per model.
            </p>
          </div>
          <div className="card">
            <h3>Can I switch plans anytime?</h3>
            <p>
              Yes — upgrades apply immediately and downgrades at the next billing cycle,
              handled through the Stripe billing portal in your dashboard.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
