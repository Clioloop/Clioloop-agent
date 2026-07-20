import { NextResponse } from "next/server";
import { fetchModels } from "@/lib/openrouter";
import { FREE_OPENROUTER_MODEL } from "@/lib/model-policy";

export const runtime = "nodejs";

// Frontier models surfaced first in the Clioloop picker for paid plans. Ordered
// by priority; ids missing from the live OpenRouter catalog are dropped
// automatically. Available to every paid tier (the full catalog is selectable).
const PAID_PICKS = [
  "deepseek/deepseek-v4-pro",
  "anthropic/claude-opus-4.8",
  "anthropic/claude-sonnet-4.6",
  "openai/gpt-5.5",
  "google/gemini-3-pro-preview",
  "x-ai/grok-4.3",
];

// Cheap/fast picks for the agent's compaction/summary model.
const COMPACTION_HINTS = ["openai/gpt-oss-20b", "google/gemma-3-12b-it"];

const wrap = (id: string) => ({ modelName: id });

/**
 * Public recommended-models feed consumed by the Clioloop CLI
 * (clio_cli/models.py::fetch_managed_recommended_models). Lets new models
 * surface in old CLI builds without a release.
 */
export async function GET() {
  try {
    const models = await fetchModels();
    const ids = new Set(models.map((m) => m.id));

    const free = ids.has(FREE_OPENROUTER_MODEL) ? [FREE_OPENROUTER_MODEL] : [];
    const paid = PAID_PICKS.filter((id) => ids.has(id));

    const firstHint = (hints: string[]) => {
      for (const hint of hints) {
        if (ids.has(hint)) return wrap(hint);
      }
      return paid.length ? wrap(paid[0]) : null;
    };
    const visionPaid = models.find((m) => m.id === "google/gemini-3-pro-preview");

    return NextResponse.json({
      paidRecommendedModels: paid.map(wrap),
      freeRecommendedModels: free.map(wrap),
      paidRecommendedCompactionModel: firstHint(COMPACTION_HINTS),
      freeRecommendedCompactionModel: free.length ? wrap(free[0]) : null,
      paidRecommendedVisionModel: visionPaid ? wrap(visionPaid.id) : null,
      freeRecommendedVisionModel: null,
    });
  } catch (err) {
    console.error("[portal] recommended models failed:", err);
    return NextResponse.json({ paidRecommendedModels: [], freeRecommendedModels: [] });
  }
}
