import { NextRequest, NextResponse } from "next/server";
import { resolveBearer } from "@/lib/tokens";
import { getSubscription } from "@/lib/db";
import { getPlan } from "@/lib/plans";
import { fetchModels } from "@/lib/openrouter";
import { FREE_OLLAMA_MODEL, ollamaCatalogEntries } from "@/lib/ollama";

export const runtime = "nodejs";

/**
 * OpenAI-compatible model list, tier-gated:
 *   free → only the one free model
 *   pro  → the open-model catalog (priced at OpenRouter-equivalent rates)
 *   max  → the open-model catalog + the full OpenRouter frontier catalog
 * Each open model carries injected `pricing` so the CLI shows price + free/paid.
 */
export async function GET(req: NextRequest) {
  const identity = resolveBearer(req.headers.get("authorization"));
  if (!identity) {
    return NextResponse.json(
      { error: "invalid_token", error_description: "Provide a valid Omni Loop Portal token" },
      { status: 401 },
    );
  }
  const plan = getPlan(getSubscription(identity.user.id)?.plan);

  try {
    const ollama = await ollamaCatalogEntries();
    let data: unknown[];
    if (plan.id === "free") {
      data = ollama.filter((m) => m.id === FREE_OLLAMA_MODEL);
    } else if (plan.id === "pro") {
      data = ollama;
    } else {
      // max / max20x: open-model catalog + the OpenRouter frontier catalog.
      data = [...ollama, ...(await fetchModels())];
    }
    return NextResponse.json({ object: "list", data });
  } catch (err) {
    console.error("[portal] model list failed:", err);
    return NextResponse.json(
      { error: "upstream_error", error_description: "Could not load the model catalog" },
      { status: 502 },
    );
  }
}
