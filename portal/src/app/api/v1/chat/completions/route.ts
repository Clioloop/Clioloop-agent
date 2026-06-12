import { NextRequest, NextResponse } from "next/server";
import { resolveBearer } from "@/lib/tokens";
import { rateLimit } from "@/lib/ratelimit";
import {
  OPENROUTER_BASE,
  checkEntitlement,
  meterUsage,
  modelAllowed,
  openRouterKey,
  usageTapStream,
} from "@/lib/openrouter";

export const runtime = "nodejs";
export const maxDuration = 300;

function apiError(status: number, code: string, message: string) {
  // OpenAI-style error envelope — what Clioloop's chat-completions client expects.
  return NextResponse.json(
    { error: { message, type: code, code } },
    { status },
  );
}

/**
 * OpenAI-compatible chat completions, proxied to OpenRouter with the portal's
 * master key. Enforces plan entitlements, gates free-tier models, forces
 * usage accounting, and meters per-user cost (streaming included).
 */
export async function POST(req: NextRequest) {
  const identity = resolveBearer(req.headers.get("authorization"));
  if (!identity) {
    return apiError(401, "invalid_token", "Provide a valid Omni Loop Portal token.");
  }

  const retry = rateLimit("inference", identity.user.id);
  if (retry !== null) {
    return apiError(429, "rate_limited", `Too many requests — try again in ${retry}s.`);
  }
  const entitlement = checkEntitlement(identity.user);
  if (!entitlement.ok) {
    return apiError(402, entitlement.errorCode ?? "entitlement", entitlement.error ?? "Not entitled.");
  }
  if (!openRouterKey()) {
    return apiError(503, "portal_not_configured", "The portal has no upstream OpenRouter key configured.");
  }

  const body = (await req.json().catch(() => null)) as Record<string, unknown> | null;
  if (!body || typeof body !== "object") {
    return apiError(400, "invalid_request", "Request body must be JSON.");
  }

  const model = String(body.model ?? "");
  if (!modelAllowed(entitlement.plan, model)) {
    return apiError(
      403,
      "model_not_in_plan",
      `The ${entitlement.plan.name} plan only includes free community models. ` +
        "Upgrade in the Omni Loop Portal to use this model.",
    );
  }

  // Always request usage accounting so we can meter cost per request.
  body.usage = { ...(typeof body.usage === "object" && body.usage ? body.usage : {}), include: true };

  const upstream = await fetch(`${OPENROUTER_BASE}/chat/completions`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${openRouterKey()}`,
      "Content-Type": "application/json",
      "HTTP-Referer": "https://github.com/Clioloop/Clioloop-agent",
      "X-Title": "Omni Loop Portal",
    },
    body: JSON.stringify(body),
  });

  const isStream = !!body.stream && upstream.ok && (upstream.headers.get("content-type") ?? "").includes("text/event-stream");
  const userId = identity.user.id;

  if (isStream && upstream.body) {
    const tapped = upstream.body.pipeThrough(
      usageTapStream((usage, usedModel) => meterUsage(userId, usedModel, usage), model),
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
    try {
      const json = JSON.parse(text) as { usage?: { prompt_tokens?: number; completion_tokens?: number; cost?: number }; model?: string };
      meterUsage(userId, json.model ?? model, json.usage);
    } catch {
      // non-JSON success body — pass through unmetered rather than failing the request
    }
  }
  return new Response(text, {
    status: upstream.status,
    headers: { "Content-Type": upstream.headers.get("content-type") ?? "application/json" },
  });
}
