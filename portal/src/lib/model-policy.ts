import type { PlanId } from "./plans";

// ─── Model access policy ─────────────────────────────────────────────────────
// All inference routes through OpenRouter (see lib/openrouter.ts). The free plan
// is limited to a single OpenRouter `:free` model; every paid tier may use the
// full OpenRouter catalog and differs only by spend allowance.
//
// User-facing copy must never expose the upstream: the provider label stays
// "Omni Loop Portal" and only model ids are shown.

/**
 * The one model that is free for the free plan (and counts toward the shared
 * daily allotment for every tier). Must be a tool-capable OpenRouter `:free`
 * model — it drives an agentic loop. Override per-deploy with
 * `FREE_OPENROUTER_MODEL` so it can track OpenRouter's changing free lineup.
 */
export const FREE_OPENROUTER_MODEL =
  process.env.FREE_OPENROUTER_MODEL?.trim() || "openai/gpt-oss-120b:free";

/** Shared daily free-model allotment, per user (UTC day). Beyond it: free tier
 *  is blocked; paid tiers keep using the free model. Abuse guard only. */
export const FREE_DAILY_REQUEST_CAP = 500;

/** Plan model-access policy: free → only the one free model; paid → any model. */
export function modelAllowedForPlan(planId: PlanId, modelId: string): boolean {
  if (planId === "free") return modelId === FREE_OPENROUTER_MODEL;
  return true; // pro / max / max20x: any OpenRouter model
}
