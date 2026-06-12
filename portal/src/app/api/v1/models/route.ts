import { NextRequest, NextResponse } from "next/server";
import { resolveBearer } from "@/lib/tokens";
import { getSubscription } from "@/lib/db";
import { getPlan, isFreeModel } from "@/lib/plans";
import { fetchModels } from "@/lib/openrouter";

export const runtime = "nodejs";

/**
 * OpenAI-compatible model list. The Clioloop CLI calls this after the device
 * login to populate its model picker; free-tier accounts only see `:free`
 * models.
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
    let models = await fetchModels();
    if (plan.freeModelsOnly) {
      models = models.filter((m) => isFreeModel(m.id));
    }
    return NextResponse.json({ object: "list", data: models });
  } catch (err) {
    console.error("[portal] model list failed:", err);
    return NextResponse.json(
      { error: "upstream_error", error_description: "Could not load the model catalog" },
      { status: 502 },
    );
  }
}
