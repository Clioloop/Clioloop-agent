import type { PlanId } from "./plans";

// ─── Model access policy ─────────────────────────────────────────────────────
// All inference routes through OpenRouter (see lib/openrouter.ts). The free plan
// is limited to a single OpenRouter `:free` model; every paid tier may use the
// full OpenRouter catalog and differs only by spend allowance.
//
// User-facing copy must never expose the upstream: the provider label stays
// "Omni Loop Portal" and only model ids are shown.

/**
 * The one model offered to free-plan users as a promotional free model.
 * Clioloop absorbs the upstream cost (it is NOT an OpenRouter `:free` model —
 * it is a paid model whose cost we cover up to FREE_DAILY_REQUEST_CAP requests
 * per day for free users, and for all users within their monthly allowance).
 * Override per-deploy with `FREE_OPENROUTER_MODEL`.
 */
export const FREE_OPENROUTER_MODEL =
  process.env.FREE_OPENROUTER_MODEL?.trim() || "z-ai/glm-5.2";

/** Shared daily free-model allotment, per user (UTC day). Beyond it: free tier
 *  is blocked; paid tiers keep using the free model. Abuse guard only. */
export const FREE_DAILY_REQUEST_CAP = 500;

/** Plan model-access policy: free → only the one free model; paid → any model. */
export function modelAllowedForPlan(planId: PlanId, modelId: string): boolean {
  if (planId === "free") return modelId === FREE_OPENROUTER_MODEL;
  return true; // pro / max / max20x: any OpenRouter model
}
