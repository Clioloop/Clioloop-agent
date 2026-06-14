import { NextRequest, NextResponse } from "next/server";
import { resolveBearer } from "@/lib/tokens";
import { rateLimit } from "@/lib/ratelimit";
import { freeModelDayCount, incrFreeModelDay, recordUsage } from "@/lib/db";
import {
  OPENROUTER_BASE,
  checkEntitlement,
  meterUsage,
  openRouterKey,
  usageTapStream,
} from "@/lib/openrouter";
import {
  FREE_DAILY_REQUEST_CAP,
  FREE_OLLAMA_MODEL,
  OLLAMA_BASE,
  isOllamaModel,
  modelAllowedForPlan,
  ollamaCostMicros,
  ollamaKey,
  ollamaPricing,
  type TokenPrice,
} from "@/lib/ollama";

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
 * OpenAI-compatible chat completions, proxied to the right upstream per model:
 * bare ids (e.g. kimi-k2.7-code, qwen3-coder:480b) → the flat-rate open-model
 * upstream; `vendor/model` ids → OpenRouter (Max only). Enforces plan model
 * access, the shared free-model daily allotment, and per-user cost metering
 * (streaming included).
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
  const ollama = isOllamaModel(model);

  // Tier model-access gate.
  if (!modelAllowedForPlan(planId, model)) {
    const message =
      planId === "free"
        ? "Your free plan includes one free model — upgrade in the Omni Loop Portal for more."
        : "This model needs the Max plan — upgrade in the Omni Loop Portal.";
    return apiError(403, "model_not_in_plan", message);
  }

  // Shared free-model daily allotment (all tiers). Free users are blocked past
  // it; pro/max keep using the free model but it becomes metered.
  let freeModelCharged = false;
  if (model === FREE_OLLAMA_MODEL) {
    const usedToday = freeModelDayCount(userId);
    if (usedToday >= FREE_DAILY_REQUEST_CAP) {
      if (planId === "free") {
        return apiError(
          429,
          "daily_limit_reached",
          "You've reached today's free usage — it resets at 00:00 UTC. Upgrade in the Omni Loop Portal for more.",
        );
      }
      freeModelCharged = true; // pro / max: continue, now metered
    }
    incrFreeModelDay(userId);
  }

  // Upstream selection + key presence.
  const upstreamBase = ollama ? OLLAMA_BASE : OPENROUTER_BASE;
  const upstreamKey = ollama ? ollamaKey() : openRouterKey();
  if (!upstreamKey) {
    return apiError(503, "portal_not_configured", "The portal has no upstream key configured for this model.");
  }

  // Usage accounting: ask both upstreams to emit a final usage object on
  // streams; OpenRouter additionally reports `cost` when usage.include is set.
  if (body.stream) {
    body.stream_options = {
      ...(typeof body.stream_options === "object" && body.stream_options ? body.stream_options : {}),
      include_usage: true,
    };
  }
  if (!ollama) {
    body.usage = { ...(typeof body.usage === "object" && body.usage ? body.usage : {}), include: true };
  }

  // Pre-resolve the Ollama price so the meter callback (incl. stream flush) is sync.
  // Free model within the daily allotment → zero price → records €0.
  const ollamaPrice: TokenPrice | null = ollama
    ? model === FREE_OLLAMA_MODEL && !freeModelCharged
      ? { prompt: 0, completion: 0 }
      : await ollamaPricing(model)
    : null;

  const meter = (usage: UpstreamUsage | undefined, usedModel: string) => {
    if (ollama && ollamaPrice) {
      if (!usage) return;
      recordUsage(
        userId,
        model,
        usage.prompt_tokens ?? 0,
        usage.completion_tokens ?? 0,
        ollamaCostMicros(usage, ollamaPrice),
      );
    } else {
      meterUsage(userId, usedModel, usage);
    }
  };

  const headers: Record<string, string> = {
    Authorization: `Bearer ${upstreamKey}`,
    "Content-Type": "application/json",
  };
  if (!ollama) {
    headers["HTTP-Referer"] = "https://github.com/Clioloop/Clioloop-agent";
    headers["X-Title"] = "Omni Loop Portal";
  }

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
    const tapped = upstream.body.pipeThrough(usageTapStream((usage, usedModel) => meter(usage, usedModel), model));
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
    try {
      const json = JSON.parse(text) as { usage?: UpstreamUsage; model?: string };
      meter(json.usage, json.model ?? model);
    } catch {
      // non-JSON success body — pass through unmetered rather than failing the request
    }
  }
  return new Response(text, {
    status: upstream.status,
    headers: { "Content-Type": upstream.headers.get("content-type") ?? "application/json" },
  });
}
