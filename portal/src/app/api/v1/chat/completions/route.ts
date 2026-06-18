import { NextRequest, NextResponse } from "next/server";
import { resolveBearer } from "@/lib/tokens";
import { rateLimit } from "@/lib/ratelimit";
import { freeModelDayCount, incrFreeModelDay } from "@/lib/db";
import { selectInferenceUpstream } from "@/lib/inference-upstream";
import {
  checkEntitlement,
  isFreeModelId,
  meterUsage,
  usageTapStream,
} from "@/lib/openrouter";
import {
  FREE_DAILY_REQUEST_CAP,
  FREE_OPENROUTER_MODEL,
  modelAllowedForPlan,
} from "@/lib/model-policy";

export const runtime = "nodejs";
export const maxDuration = 300;

function apiError(status: number, code: string, message: string) {
  // OpenAI-style error envelope — what Clioloop's chat-completions client expects.
  return NextResponse.json({ error: { message, type: code, code } }, { status });
}

interface UpstreamUsage {
  prompt_tokens?: number;
  completion_tokens?: number;
  cost?: number;
}

/**
 * OpenAI-compatible chat completions, proxied to OpenRouter. Enforces plan model
 * access (free → the one free model; paid → any), the shared free-model daily
 * allotment, and per-user cost metering (streaming included).
 */
export async function POST(req: NextRequest) {
  const identity = resolveBearer(req.headers.get("authorization"));
  if (!identity) {
    return apiError(401, "invalid_token", "Provide a valid Omni Loop Portal token.");
  }
  const userId = identity.user.id;

  const retry = rateLimit("inference", userId);
  if (retry !== null) {
    return apiError(429, "rate_limited", `Too many requests — try again in ${retry}s.`);
  }
  const entitlement = checkEntitlement(identity.user);
  if (!entitlement.ok) {
    return apiError(402, entitlement.errorCode ?? "entitlement", entitlement.error ?? "Not entitled.");
  }

  const body = (await req.json().catch(() => null)) as Record<string, unknown> | null;
  if (!body || typeof body !== "object") {
    return apiError(400, "invalid_request", "Request body must be JSON.");
  }

  const model = String(body.model ?? "");
  const planId = entitlement.plan.id;
  const requirePaidMetering = planId !== "free" && !isFreeModelId(model);

  // Tier model-access gate.
  if (!modelAllowedForPlan(planId, model)) {
    const message =
      planId === "free"
        ? "Your free plan includes one free model — upgrade in the Omni Loop Portal for more."
        : "This model isn't available on your plan — upgrade in the Omni Loop Portal.";
    return apiError(403, "model_not_in_plan", message);
  }
  // No metering pre-block: meterUsage self-heals a missing/zero upstream cost via
  // the catalog price (see lib/openrouter.meterUsage), so a model is never made
  // unavailable for a metering hiccup.

  // Shared free-model daily allotment (all tiers, abuse guard). Free users are
  // blocked past it; paid tiers keep using the free model.
  if (model === FREE_OPENROUTER_MODEL) {
    const usedToday = freeModelDayCount(userId);
    if (usedToday >= FREE_DAILY_REQUEST_CAP && planId === "free") {
      return apiError(
        429,
        "daily_limit_reached",
        "You've reached today's free usage — it resets at 00:00 UTC. Upgrade in the Omni Loop Portal for more.",
      );
    }
    incrFreeModelDay(userId);
  }

  // Upstream selection + key presence.
  const selectedUpstream = selectInferenceUpstream();
  const upstreamBase = selectedUpstream.base;
  const upstreamKey = selectedUpstream.key;
  if (!upstreamKey) {
    return apiError(503, "portal_not_configured", "The portal has no upstream key configured.");
  }

  // Usage accounting: ask OpenRouter to emit a final usage object (incl. `cost`)
  // on streams and non-streams.
  if (body.stream) {
    body.stream_options = {
      ...(typeof body.stream_options === "object" && body.stream_options ? body.stream_options : {}),
      include_usage: true,
    };
  }
  body.usage = { ...(typeof body.usage === "object" && body.usage ? body.usage : {}), include: true };

  const meter = (usage: UpstreamUsage | undefined, usedModel: string) => {
    meterUsage(userId, usedModel, usage, {
      requirePositiveCost: planId !== "free" && !isFreeModelId(usedModel),
      path: "chat",
    });
  };

  const headers: Record<string, string> = {
    Authorization: `Bearer ${upstreamKey}`,
    "Content-Type": "application/json",
    "HTTP-Referer": "https://github.com/Clioloop/Clioloop-agent",
    "X-Title": "Omni Loop Portal",
  };

  const upstream = await fetch(`${upstreamBase}/chat/completions`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });

  const isStream =
    !!body.stream &&
    upstream.ok &&
    (upstream.headers.get("content-type") ?? "").includes("text/event-stream");

  if (isStream && upstream.body) {
    const tapped = upstream.body.pipeThrough(
      usageTapStream(
        (usage, usedModel) => meter(usage, usedModel),
        model,
        // No final usage chunk: still record the call (meterUsage falls back to
        // the catalog price, or a floor) so a streamed turn is never unbilled.
        (usedModel) => meter(undefined, usedModel),
      ),
    );
    return new Response(tapped, {
      status: upstream.status,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      },
    });
  }

  const text = await upstream.text();
  if (upstream.ok) {
    // meterUsage never throws — it self-heals a missing/zero cost via the
    // catalog price (or a floor), so we always bill and never block the response.
    try {
      const json = JSON.parse(text) as { usage?: UpstreamUsage; model?: string };
      meter(json.usage, json.model ?? model);
    } catch {
      // Non-JSON success body (no parseable usage) — still record the call so a
      // paid response is never delivered unbilled.
      if (requirePaidMetering) meter(undefined, model);
    }
  }
  return new Response(text, {
    status: upstream.status,
    headers: { "Content-Type": upstream.headers.get("content-type") ?? "application/json" },
  });
}
