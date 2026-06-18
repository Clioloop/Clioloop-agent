import type { Metadata } from "next";
import { PLANS, PLAN_ORDER, type PlanId } from "@/lib/plans";
import PlanButton from "@/components/PlanButton";

export const metadata: Metadata = {
  title: "Pricing — Agentic Fusion, 300+ models, one login",
  description:
    "Clioloop plans: start free with one model, or go Pro for 300+ models, the full tool gateway and Agentic Fusion. Max and Max 10x add video generation and 5×/10× usage. No API keys.",
  alternates: { canonical: "/pricing" },
};

const FLAGS: Record<string, string | undefined> = {
  pro: "Most popular",
  max20x: "Best for fleets",
};

// Per-tier feature lines tuned for the cards. Each line carries an optional
// kind: "fusion" highlights Agentic Fusion (Pro+), "off" marks a not-included
// line (Free → no hosted tools). Data mirrors lib/plans.ts.
type Line = { text: string; kind?: "fusion" | "off" };
const FEATURES: Record<PlanId, Line[]> = {
  free: [
    { text: "1 free model to try" },
    { text: "No hosted tools — no web, image, TTS or browser", kind: "off" },
    { text: "No Agentic Fusion (Pro and up)", kind: "off" },
    { text: "1 connected device" },
    { text: "Card verification required — never charged" },
  ],
  pro: [
    { text: "Full 300+ OpenRouter model catalog" },
    { text: "Agentic Fusion — planners + reviewers fuse one answer", kind: "fusion" },
    { text: "Tool gateway: web search & extract · image gen · premium TTS · cloud browser" },
    { text: "Unlimited devices" },
    { text: "Usage dashboard" },
    { text: "Email support" },
  ],
  max: [
    { text: "300+ frontier models — Claude, GPT, Gemini, Grok" },
    { text: "Everything in Pro, incl. Agentic Fusion", kind: "fusion" },
    { text: "Video generation" },
    { text: "5× Pro monthly usage" },
    { text: "Long-running agent loops" },
    { text: "Priority routing & support" },
  ],
  max20x: [
    { text: "Everything in Max, incl. Agentic Fusion", kind: "fusion" },
    { text: "10× Pro monthly usage" },
    { text: "Parallel agent swarms" },
    { text: "Highest priority routing" },
    { text: "Direct support channel" },
  ],
};

const FAQ = [
  {
    q: "Why does Free need a card?",
    a: "A one-time card verification keeps bots and abuse off the free model. You are never charged on the Free plan — verification is a €0 authorization.",
  },
  {
    q: "What does Agentic Fusion cost?",
    a: "Fusion is included from Pro upward at no extra fee. The planner and reviewer model calls are metered against your normal monthly usage allowance, like any other inference.",
  },
  {
    q: "What does “usage” mean?",
    a: "Each request is metered at the upstream model's real cost. Your plan includes a monthly allowance; the dashboard shows live consumption per month and per model.",
  },
  {
    q: "Can I switch plans anytime?",
    a: "Yes — upgrades apply immediately and downgrades at the next billing cycle, handled through the Stripe billing portal in your dashboard.",
  },
];

const FAQ_JSONLD = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  mainEntity: FAQ.map((f) => ({
    "@type": "Question",
    name: f.q,
    acceptedAnswer: { "@type": "Answer", text: f.a },
  })),
};

export default function PricingPage() {
  return (
    <div className="page">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(FAQ_JSONLD) }}
      />
      <div className="container">
        <div className="section-head fade-up" style={{ marginTop: 24 }}>
          <span className="eyebrow">pricing</span>
          <h2>One login. Every model. Agentic Fusion.</h2>
          <p>
            Every plan includes the full Clioloop experience: one-click setup on CLI,
            TUI, desktop and dashboard, streaming inference, usage metering and rotating
            device tokens. No API keys — your subscription is the credential. Hosted tools
            and Agentic Fusion unlock on Pro.
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
                  {FEATURES[id].map((f) => (
                    <li
                      key={f.text}
                      className={f.kind === "fusion" ? "li-fusion" : f.kind === "off" ? "li-off" : undefined}
                    >
                      {f.text}
                    </li>
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
        <div className="grid-2">
          {FAQ.map((f) => (
            <div className="card" key={f.q}>
              <h3>{f.q}</h3>
              <p>{f.a}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
