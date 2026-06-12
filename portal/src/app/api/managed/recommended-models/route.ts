import { NextResponse } from "next/server";
import { fetchModels } from "@/lib/openrouter";
import { isFreeModel } from "@/lib/plans";

export const runtime = "nodejs";

// Frontier picks surfaced first in the Clioloop model picker. Order matters;
// entries missing from the live OpenRouter catalog are dropped automatically.
const PAID_PICK_PREFIXES = [
  "anthropic/claude",
  "openai/gpt",
  "google/gemini",
  "x-ai/grok",
  "deepseek/deepseek",
  "qwen/qwen",
  "moonshotai/kimi",
  "mistralai/",
  "meta-llama/",
];

const COMPACTION_HINTS = ["google/gemini-2.5-flash", "openai/gpt-4o-mini", "anthropic/claude-haiku"];

const wrap = (id: string) => ({ modelName: id });

/**
 * Public recommended-models feed consumed by the Clioloop CLI
 * (clio_cli/models.py::fetch_managed_recommended_models). Lets new models
 * surface in old CLI builds without a release.
 */
export async function GET() {
  try {
    const models = await fetchModels();
    const ids = models.map((m) => m.id);

    const free = ids.filter(isFreeModel).slice(0, 40);
    const paid: string[] = [];
    for (const prefix of PAID_PICK_PREFIXES) {
      for (const id of ids) {
        if (id.startsWith(prefix) && !isFreeModel(id) && !paid.includes(id)) {
          paid.push(id);
          if (paid.length >= 40) break;
        }
      }
      if (paid.length >= 40) break;
    }

    const firstMatch = (hints: string[], pool: string[]) => {
      for (const hint of hints) {
        const hit = pool.find((id) => id.startsWith(hint));
        if (hit) return wrap(hit);
      }
      return pool.length ? wrap(pool[0]) : null;
    };

    const visionPaid = models
      .filter((m) => !isFreeModel(m.id) && JSON.stringify(m.architecture ?? "").includes("image"))
      .map((m) => m.id);
    const visionFree = models
      .filter((m) => isFreeModel(m.id) && JSON.stringify(m.architecture ?? "").includes("image"))
      .map((m) => m.id);

    return NextResponse.json({
      paidRecommendedModels: paid.map(wrap),
      freeRecommendedModels: free.map(wrap),
      paidRecommendedCompactionModel: firstMatch(COMPACTION_HINTS, paid),
      freeRecommendedCompactionModel: free.length ? wrap(free[0]) : null,
      paidRecommendedVisionModel: visionPaid.length ? wrap(visionPaid[0]) : null,
      freeRecommendedVisionModel: visionFree.length ? wrap(visionFree[0]) : null,
    });
  } catch (err) {
    console.error("[portal] recommended models failed:", err);
    return NextResponse.json({ paidRecommendedModels: [], freeRecommendedModels: [] });
  }
}
