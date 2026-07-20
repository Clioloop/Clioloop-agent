import type { PlanId } from "./plans";

// ─── Model access policy ─────────────────────────────────────────────────────
// All inference routes through OpenRouter (see lib/openrouter.ts). The free plan
// is limited to a single promotional OpenRouter model; every paid tier may use the
// full OpenRouter catalog and differs only by spend allowance.
//
// User-facing copy must never expose the upstream: the provider label stays
// "Omni Loop Portal" and only model ids are shown.

/**
 * The one model offered to free-plan users as a promotional free model.
 * Clioloop absorbs the upstream cost (it is NOT an OpenRouter `:free` model —
 * it is a paid model whose cost we cover up to FREE_DAILY_REQUEST_CAP requests
 * per day for free users, and for all users within their monthly allowance).
 * Override per-deploy with `FREE_OPENROUTER_MODEL`. The former GLM 5.2 promo
 * value is intentionally ignored so a stale deployment variable cannot keep
 * granting GLM free access after the DeepSeek migration.
 */
const DEFAULT_FREE_OPENROUTER_MODEL = "deepseek/deepseek-v4-pro";
const configuredFreeModel = process.env.FREE_OPENROUTER_MODEL?.trim();
export const FREE_OPENROUTER_MODEL =
  configuredFreeModel && configuredFreeModel !== "z-ai/glm-5.2"
    ? configuredFreeModel
    : DEFAULT_FREE_OPENROUTER_MODEL;

/** Shared daily free-model allotment, per user (UTC day). Beyond it: free tier
 *  is blocked; paid tiers keep using the free model. Abuse guard only. */
export const FREE_DAILY_REQUEST_CAP = 500;

/** Plan model-access policy: free → only the one free model; paid → any model. */
export function modelAllowedForPlan(planId: PlanId, modelId: string): boolean {
  if (planId === "free") return modelId === FREE_OPENROUTER_MODEL;
  return true; // pro / max / max20x: any OpenRouter model
}
