import { NextRequest, NextResponse } from "next/server";
import { withBearer } from "@/lib/handlers";
import { getSubscription } from "@/lib/db";
import { getPlan } from "@/lib/plans";
import { fetchModels } from "@/lib/openrouter";
import { FREE_OPENROUTER_MODEL } from "@/lib/model-policy";

export const runtime = "nodejs";

/**
 * OpenAI-compatible model list, tier-gated:
 *   free → only the one free model
 *   paid → the full OpenRouter catalog
 * Each entry carries OpenRouter `pricing` so the CLI shows price + free/paid.
 */
export const GET = withBearer(async (_req: NextRequest, identity) => {
  const plan = getPlan(getSubscription(identity.user.id)?.plan);

  try {
    const all = await fetchModels();
    const data =
      plan.id === "free" ? all.filter((m) => m.id === FREE_OPENROUTER_MODEL) : all;
    return NextResponse.json({ object: "list", data });
  } catch (err) {
    console.error("[portal] model list failed:", err);
    return NextResponse.json(
      { error: "upstream_error", error_description: "Could not load the model catalog" },
      { status: 502 },
    );
  }
}, {
  unauthorized: () =>
    NextResponse.json(
      { error: "invalid_token", error_description: "Provide a valid Omni Loop Portal token" },
      { status: 401 },
    ),
});
