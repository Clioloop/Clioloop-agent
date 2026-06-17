import { getSubscription, monthUsageMicros, recordUsage, UserRow } from "./db";
import { getPlan, isFreeModel, Plan } from "./plans";

export const OPENROUTER_BASE = "https://openrouter.ai/api/v1";

export function openRouterKey(): string {
  return process.env.OPENROUTER_API_KEY?.trim() ?? "";
}

export interface Entitlement {
  ok: boolean;
  plan: Plan;
  usedMicros: number;
  limitMicros: number;
  error?: string;
  errorCode?: string;
}

/** Check whether `user` may run inference right now (plan + budget + card). */
export function checkEntitlement(user: UserRow): Entitlement {
  const sub = getSubscription(user.id);
  const plan = getPlan(sub?.plan);
  const usedMicros = monthUsageMicros(user.id);
  const limitMicros = plan.monthlyCreditsMicros;

  if (plan.requiresCardVerification && !user.card_verified) {
    return {
      ok: false, plan, usedMicros, limitMicros,
      errorCode: "card_verification_required",
      error:
        "Your free plan needs a one-time card verification (you will never be charged). " +
        "Visit your Omni Loop Portal dashboard to verify.",
    };
  }
  if (sub?.status === "past_due") {
    return {
      ok: false, plan, usedMicros, limitMicros,
      errorCode: "payment_past_due",
      error: "Your subscription payment is past due. Update your payment method in the portal.",
    };
  }
  if (usedMicros >= limitMicros) {
    return {
      ok: false, plan, usedMicros, limitMicros,
      errorCode: "quota_exhausted",
      error:
        `You've used your ${plan.name} plan's monthly allowance. ` +
        "Upgrade your plan in the Omni Loop Portal to keep going.",
    };
  }
  return { ok: true, plan, usedMicros, limitMicros };
}

export function modelAllowed(plan: Plan, modelId: string): boolean {
  return !plan.freeModelsOnly || isFreeModel(modelId);
}

interface UpstreamUsage {
  prompt_tokens?: number;
  completion_tokens?: number;
  cost?: number; // USD credits, present when usage.include is requested
}

export function meterUsage(userId: string, model: string, usage: UpstreamUsage | undefined): void {
  if (!usage) return;
  const costMicros = Math.max(0, Math.round((usage.cost ?? 0) * 1_000_000));
  recordUsage(
    userId,
    model,
    usage.prompt_tokens ?? 0,
    usage.completion_tokens ?? 0,
    costMicros,
  );
}

// ─── Model catalog (cached) ──────────────────────────────────────────────────

interface ModelEntry {
  id: string;
  name?: string;
  description?: string;
  context_length?: number;
  pricing?: Record<string, string>;
  [k: string]: unknown;
}

declare global {
  var __olpModelCache: { at: number; data: ModelEntry[] } | undefined;
}

const MODEL_CACHE_TTL_MS = 5 * 60 * 1000;

export async function fetchModels(): Promise<ModelEntry[]> {
  const cache = globalThis.__olpModelCache;
  if (cache && Date.now() - cache.at < MODEL_CACHE_TTL_MS) return cache.data;
  const res = await fetch(`${OPENROUTER_BASE}/models`, {
    headers: openRouterKey() ? { Authorization: `Bearer ${openRouterKey()}` } : {},
  });
  if (!res.ok) throw new Error(`OpenRouter /models failed: ${res.status}`);
  const payload = (await res.json()) as { data?: ModelEntry[] };
  const data = Array.isArray(payload.data) ? payload.data : [];
  globalThis.__olpModelCache = { at: Date.now(), data };
  return data;
}

/**
 * Watch an OpenAI-style SSE stream for the final `usage` object while
 * passing bytes through untouched. Only a small line buffer is retained.
 */
export function usageTapStream(
  onUsage: (usage: UpstreamUsage, model: string) => void,
  fallbackModel: string,
): TransformStream<Uint8Array, Uint8Array> {
  const decoder = new TextDecoder();
  let lineBuf = "";
  let lastUsage: UpstreamUsage | undefined;
  let lastModel = fallbackModel;

  const scan = (text: string, final = false) => {
    lineBuf += text;
    const lines = lineBuf.split("\n");
    lineBuf = final ? "" : lines.pop() ?? "";
    for (const line of lines) {
      const data = line.startsWith("data:") ? line.slice(5).trim() : "";
      if (!data || data === "[DONE]") continue;
      try {
        const obj = JSON.parse(data) as { usage?: UpstreamUsage; model?: string };
        if (obj.usage) lastUsage = obj.usage;
        if (obj.model) lastModel = obj.model;
      } catch {
        // partial / non-JSON keep-alive line — ignore
      }
    }
    // Guard against a pathological never-newline stream growing the buffer.
    if (lineBuf.length > 262_144) lineBuf = lineBuf.slice(-65_536);
  };

  return new TransformStream<Uint8Array, Uint8Array>({
    transform(chunk, controller) {
      controller.enqueue(chunk);
      scan(decoder.decode(chunk, { stream: true }));
    },
    flush() {
      scan(decoder.decode(), true);
      if (lastUsage) onUsage(lastUsage, lastModel);
    },
  });
}
