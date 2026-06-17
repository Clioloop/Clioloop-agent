// ─── Subscription tiers ──────────────────────────────────────────────────────
// All inference usage is metered in "credit micros": 1_000_000 micros = one
// OpenRouter USD credit of upstream model spend. Plan prices are charged in EUR,
// so allowances intentionally leave room for FX movement, OpenRouter credit
// fees, Stripe fees, and gross margin. Adjust `monthlyCreditsMicros` to tune
// margins.
//
// Margin policy: allowances are set so a fully-drained subscription keeps a
// 25–40% gross margin (Pro/Max 25%, Max 10x 40%) before Stripe fees. Most
// subscribers never drain the allowance, so realized margins are higher.

export type PlanId = "free" | "pro" | "max" | "max20x";

/**
 * Bundled tool-gateway services (mirrors the Clioloop agent's managed
 * feature keys in clio_cli/portal_subscription.py). `video_gen` is the
 * expensive one — reserved for Max tiers.
 */
export type ServiceKey = "web" | "browser" | "image_gen" | "video_gen" | "tts";

export interface Plan {
  id: PlanId;
  name: string;
  priceEur: number;
  /** Monthly inference allowance, in credit micros (1e6 = €1 upstream). */
  monthlyCreditsMicros: number;
  /** Legacy flag (kept for compatibility). Tier model access is now decided by
   *  `modelAllowedForPlan` in lib/model-policy.ts: free → the one free model;
   *  every paid tier → the full OpenRouter catalog. */
  freeModelsOnly: boolean;
  /** Requires a verified card on file before inference is allowed. */
  requiresCardVerification: boolean;
  /** Tool-gateway services bundled with this plan. */
  services: ServiceKey[];
  tagline: string;
  features: string[];
  stripePriceEnv?: string;
}

export const PLANS: Record<PlanId, Plan> = {
  free: {
    id: "free",
    name: "Free",
    priceEur: 0,
    monthlyCreditsMicros: 1_000_000, // €1/mo of free-model headroom
    freeModelsOnly: true,
    requiresCardVerification: true,
    services: [],
    tagline: "Try Clioloop with a free model",
    features: [
      "A capable free model",
      "Web search & extract on Pro and up",
      "1 connected device",
      "Card verification required — never charged",
    ],
  },
  pro: {
    id: "pro",
    name: "Pro",
    priceEur: 20,
    monthlyCreditsMicros: 15_000_000, // €15 upstream → 25% worst-case margin
    freeModelsOnly: false,
    requiresCardVerification: false,
    services: ["web", "browser", "image_gen", "tts"],
    tagline: "300+ OpenRouter models, one subscription",
    features: [
      "Access to the full OpenRouter model catalog",
      "✦ Agentic Fusion — planners + reviewers fuse one answer",
      "Self-hosted web search & extract · image gen · premium TTS · cloud browser",
      "Unlimited devices",
      "Usage dashboard",
      "Email support",
    ],
    stripePriceEnv: "STRIPE_PRICE_PRO",
  },
  max: {
    id: "max",
    name: "Max",
    priceEur: 100,
    monthlyCreditsMicros: 75_000_000, // 5× Pro → 25% worst-case margin
    freeModelsOnly: false,
    requiresCardVerification: false,
    services: ["web", "browser", "image_gen", "video_gen", "tts"],
    tagline: "300+ frontier models — 5× Pro usage",
    features: [
      "300+ frontier models — Claude, GPT, Gemini, Grok",
      "Everything in Pro (incl. ✦ Agentic Fusion)",
      "5× Pro monthly usage",
      "Video generation",
      "Long-running agent loops",
      "Priority routing & support",
    ],
    stripePriceEnv: "STRIPE_PRICE_MAX",
  },
  max20x: {
    id: "max20x",
    name: "Max 10x",
    priceEur: 250,
    monthlyCreditsMicros: 150_000_000, // 10× Pro → 40% worst-case margin
    freeModelsOnly: false,
    requiresCardVerification: false,
    services: ["web", "browser", "image_gen", "video_gen", "tts"],
    tagline: "10× Pro usage for heavy fleets and swarms",
    features: [
      "Everything in Max",
      "10× Pro monthly usage",
      "Parallel agent swarms",
      "Highest priority routing",
      "Direct support channel",
    ],
    stripePriceEnv: "STRIPE_PRICE_MAX20X",
  },
};

export const PLAN_ORDER: PlanId[] = ["free", "pro", "max", "max20x"];

export function getPlan(id: string | null | undefined): Plan {
  return PLANS[(id as PlanId) ?? "free"] ?? PLANS.free;
}

export function isFreeModel(modelId: string): boolean {
  return modelId.endsWith(":free");
}

/** Plans entitled to Model Fusion (Pro and up). Mirrors FUSION_PLAN_IDS in the
 *  agent's fusion_engine.py. The server-side Fusion endpoints enforce this. */
export function planAllowsFusion(planId: PlanId): boolean {
  return planId !== "free";
}
