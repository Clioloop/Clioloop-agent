import { NextResponse } from "next/server";
import { FREE_OLLAMA_MODEL, fetchOllamaModels } from "@/lib/ollama";

export const runtime = "nodejs";

// Recommended open models surfaced first in the Clioloop picker. Ordered by
// priority; ids missing from the live catalog are dropped automatically. These
// are all open models (work for Pro AND Max); Max additionally gets the full
// frontier catalog from /api/v1/models, so no OpenRouter ids are recommended
// here (which would otherwise show as unselectable for Pro).
const PAID_PICK_PREFIXES = [
  "qwen3-coder",
  "kimi-k2",
  "deepseek-v3",
  "glm-",
  "gpt-oss",
  "qwen3-next",
  "minimax-m",
  "qwen3-vl",
  "mistral-large",
  "nemotron-3-super",
];

// Cheap/fast picks for the agent's compaction/summary model.
const COMPACTION_HINTS = ["gpt-oss:20b", "qwen3-coder-next", "gemma3:12b", "nemotron-3-nano"];

const wrap = (id: string) => ({ modelName: id });

/**
 * Public recommended-models feed consumed by the Clioloop CLI
 * (clio_cli/models.py::fetch_managed_recommended_models). Lets new models
 * surface in old CLI builds without a release.
 */
export async function GET() {
  try {
    const ids = await fetchOllamaModels();

    const free = ids.includes(FREE_OLLAMA_MODEL) ? [FREE_OLLAMA_MODEL] : [];

    const paid: string[] = [];
    for (const prefix of PAID_PICK_PREFIXES) {
      for (const id of ids) {
        if (id !== FREE_OLLAMA_MODEL && id.startsWith(prefix) && !paid.includes(id)) {
          paid.push(id);
        }
      }
    }

    const firstHint = (hints: string[]) => {
      for (const hint of hints) {
        const hit = ids.find((id) => id.startsWith(hint));
        if (hit) return wrap(hit);
      }
      return paid.length ? wrap(paid[0]) : null;
    };
    const visionPaid = ids.find((id) => id.startsWith("qwen3-vl"));

    return NextResponse.json({
      paidRecommendedModels: paid.map(wrap),
      freeRecommendedModels: free.map(wrap),
      paidRecommendedCompactionModel: firstHint(COMPACTION_HINTS),
      freeRecommendedCompactionModel: free.length ? wrap(free[0]) : null,
      paidRecommendedVisionModel: visionPaid ? wrap(visionPaid) : null,
      freeRecommendedVisionModel: null,
    });
  } catch (err) {
    console.error("[portal] recommended models failed:", err);
    return NextResponse.json({ paidRecommendedModels: [], freeRecommendedModels: [] });
  }
}
