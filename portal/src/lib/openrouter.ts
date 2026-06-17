import {
  getSubscription,
  hasActiveMeteringAlert,
  monthUsageMicros,
  recordMeteringAlert,
  recordUsage,
  UserRow,
} from "./db";
import { FREE_OPENROUTER_MODEL } from "./model-policy";
import { getPlan, Plan } from "./plans";

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
  return !plan.freeModelsOnly || modelId === FREE_OPENROUTER_MODEL;
}

interface UpstreamUsage {
  prompt_tokens?: number;
  completion_tokens?: number;
  cost?: number; // USD credits, present when usage.include is requested
}

export class MeteringError extends Error {
  constructor(
    message: string,
    public readonly reason: "missing_usage" | "missing_cost" | "non_positive_cost",
  ) {
    super(message);
    this.name = "MeteringError";
  }
}

export interface MeterUsageOptions {
  requirePositiveCost?: boolean;
  path?: string;
}

export interface MeterUsageResult {
  recorded: boolean;
  costMicros: number;
}

export function isFreeModelId(model: string): boolean {
  return model.endsWith(":free");
}

export function meteringBlocked(model: string, pathName = "chat"): boolean {
  return hasActiveMeteringAlert(model, pathName);
}

export function noteMeteringAlert(
  model: string,
  pathName: string,
  reason: string,
  details = "",
): void {
  recordMeteringAlert(model, pathName, reason, details);
}

function validateUsage(
  model: string,
  usage: UpstreamUsage | undefined,
  options: MeterUsageOptions,
): UpstreamUsage | undefined {
  if (!options.requirePositiveCost) return usage;
  if (!usage) {
    noteMeteringAlert(model, options.path ?? "chat", "missing_usage");
    throw new MeteringError("OpenRouter response was missing usage data.", "missing_usage");
  }
  if (typeof usage.cost !== "number" || !Number.isFinite(usage.cost)) {
    noteMeteringAlert(model, options.path ?? "chat", "missing_cost", JSON.stringify(usage));
    throw new MeteringError("OpenRouter response was missing usage.cost.", "missing_cost");
  }
  if (usage.cost <= 0) {
    noteMeteringAlert(model, options.path ?? "chat", "non_positive_cost", JSON.stringify(usage));
    throw new MeteringError("OpenRouter response reported a non-positive paid cost.", "non_positive_cost");
  }
  return usage;
}

export function meterUsage(
  userId: string,
  model: string,
  usage: UpstreamUsage | undefined,
  options: MeterUsageOptions = {},
): MeterUsageResult {
  const checked = validateUsage(model, usage, options);
  if (!checked) return { recorded: false, costMicros: 0 };
  const rounded = Math.round((checked.cost ?? 0) * 1_000_000);
  const costMicros = options.requirePositiveCost ? Math.max(1, rounded) : Math.max(0, rounded);
  recordUsage(
    userId,
    model,
    checked.prompt_tokens ?? 0,
    checked.completion_tokens ?? 0,
    costMicros,
  );
  return { recorded: true, costMicros };
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
  const data = Array.isArray(payload.data) ? payload.data.filter(isTextOutputModel) : [];
  globalThis.__olpModelCache = { at: Date.now(), data };
  return data;
}

export function isTextOutputModel(model: ModelEntry): boolean {
  const output = model.architecture && typeof model.architecture === "object"
    ? (model.architecture as { output_modalities?: unknown }).output_modalities
    : undefined;
  return !Array.isArray(output) || output.includes("text");
}

/**
 * Watch an OpenAI-style SSE stream for the final `usage` object while
 * passing bytes through untouched. Only a small line buffer is retained.
 */
export function usageTapStream(
  onUsage: (usage: UpstreamUsage, model: string) => void,
  fallbackModel: string,
  onMissingUsage?: (model: string) => void,
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
      else onMissingUsage?.(lastModel);
    },
  });
}
