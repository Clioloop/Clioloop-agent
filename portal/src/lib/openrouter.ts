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
      ok: false,
      plan,
      usedMicros,
      limitMicros,
      errorCode: "card_verification_required",
      error:
        "Your free plan needs a one-time card verification (you will never be charged). " +
        "Visit your Omni Loop Portal dashboard to verify.",
    };
  }
  if (sub?.status === "past_due") {
    return {
      ok: false,
      plan,
      usedMicros,
      limitMicros,
      errorCode: "payment_past_due",
      error:
        "Your subscription payment is past due. Update your payment method in the portal.",
    };
  }
  if (usedMicros >= limitMicros) {
    return {
      ok: false,
      plan,
      usedMicros,
      limitMicros,
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

export interface MeterUsageOptions {
  requirePositiveCost?: boolean;
  path?: string;
}

export interface MeterUsageResult {
  recorded: boolean;
  costMicros: number;
}

const DEFAULT_MISSING_USAGE_PROMPT_TOKEN_FLOOR = 8_192;
const DEFAULT_MISSING_USAGE_COMPLETION_TOKEN_FLOOR = 8_192;
const DEFAULT_UNKNOWN_PAID_PROMPT_PRICE_USD = 0.00002; // $20 / 1M tokens.
const DEFAULT_UNKNOWN_PAID_COMPLETION_PRICE_USD = 0.0001; // $100 / 1M tokens.

function positiveEnvNumber(name: string, fallback: number): number {
  const raw = process.env[name]?.trim();
  if (!raw) return fallback;
  const value = Number(raw);
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

function paidMeteringTokenFloors(
  promptTokens: number,
  completionTokens: number,
) {
  return {
    promptTokens:
      promptTokens > 0
        ? promptTokens
        : positiveEnvNumber(
            "METERING_MISSING_USAGE_PROMPT_TOKEN_FLOOR",
            DEFAULT_MISSING_USAGE_PROMPT_TOKEN_FLOOR,
          ),
    completionTokens:
      completionTokens > 0
        ? completionTokens
        : positiveEnvNumber(
            "METERING_MISSING_USAGE_COMPLETION_TOKEN_FLOOR",
            DEFAULT_MISSING_USAGE_COMPLETION_TOKEN_FLOOR,
          ),
  };
}

function modelPriceLookupIds(model: string): string[] {
  const ids = [model];
  const withoutDatedSuffix = model.replace(/-\d{8}$/, "");
  if (withoutDatedSuffix !== model) ids.push(withoutDatedSuffix);
  return ids;
}

function unknownPaidModelPriceMicros(
  promptTokens: number,
  completionTokens: number,
): number {
  const promptPrice = positiveEnvNumber(
    "METERING_UNKNOWN_PAID_PROMPT_PRICE_USD",
    DEFAULT_UNKNOWN_PAID_PROMPT_PRICE_USD,
  );
  const completionPrice = positiveEnvNumber(
    "METERING_UNKNOWN_PAID_COMPLETION_PRICE_USD",
    DEFAULT_UNKNOWN_PAID_COMPLETION_PRICE_USD,
  );
  const usd = promptTokens * promptPrice + completionTokens * completionPrice;
  return Math.max(1, Math.round(usd * 1_000_000));
}

export function isFreeModelId(model: string): boolean {
  return model.endsWith(":free");
}

export function meteringBlocked(...args: unknown[]): boolean {
  // Metering now self-heals: when OpenRouter omits a usable cost we charge from
  // the catalog price (see meterUsage), so a model is never blocked for a
  // missing/zero upstream cost. Kept for call-site compatibility — always false.
  // (hasActiveMeteringAlert stays available as an informational query.)
  void args;
  void hasActiveMeteringAlert;
  return false;
}

export function noteMeteringAlert(
  model: string,
  pathName: string,
  reason: string,
  details = "",
): void {
  recordMeteringAlert(model, pathName, reason, details);
}

/**
 * Best-effort cost in micros for a model, computed from the cached OpenRouter
 * catalog price (per-token USD) × token counts. Returns null when the model or
 * its pricing isn't in the cache, or the result isn't a usable positive number.
 * Synchronous: it only reads the already-cached catalog (warmed by fetchModels).
 */
export function modelPriceMicros(
  model: string,
  promptTokens: number,
  completionTokens: number,
): number | null {
  const cache = globalThis.__olpModelCache;
  if (!cache) return null;
  const ids = new Set(modelPriceLookupIds(model));
  const pricing = cache.data.find((m) => ids.has(m.id))?.pricing;
  if (!pricing) return null;
  const promptPrice = Number(pricing.prompt);
  const completionPrice = Number(pricing.completion);
  if (!Number.isFinite(promptPrice) || !Number.isFinite(completionPrice))
    return null;
  const usd = promptTokens * promptPrice + completionTokens * completionPrice;
  if (!Number.isFinite(usd) || usd <= 0) return null;
  return Math.max(1, Math.round(usd * 1_000_000));
}

let _warmingCatalog = false;
/** Populate the model-price cache in the background (5-min TTL) without blocking. */
function warmModelCatalog(): void {
  if (_warmingCatalog) return;
  _warmingCatalog = true;
  void fetchModels()
    .catch(() => {})
    .finally(() => {
      _warmingCatalog = false;
    });
}

/**
 * Record a usage event for an inference call. Cost comes from OpenRouter's
 * `usage.cost` when present and positive; otherwise — for paid models — it falls
 * back to the catalog price × tokens. If OpenRouter returns an uncataloged paid
 * model or omits token counts, a conservative no-loss fallback is used and a
 * metering alert is recorded. It never throws and never blocks a model.
 */
export function meterUsage(
  userId: string,
  model: string,
  usage: UpstreamUsage | undefined,
  options: MeterUsageOptions = {},
): MeterUsageResult {
  const requirePositive = !!options.requirePositiveCost;
  const path = options.path ?? "chat";
  const promptTokens = usage?.prompt_tokens ?? 0;
  const completionTokens = usage?.completion_tokens ?? 0;
  const upstreamCost =
    typeof usage?.cost === "number" && Number.isFinite(usage.cost)
      ? usage.cost
      : null;

  let costMicros: number;
  if (upstreamCost !== null && upstreamCost > 0) {
    // Authoritative cost from OpenRouter.
    costMicros = Math.max(
      requirePositive ? 1 : 0,
      Math.round(upstreamCost * 1_000_000),
    );
  } else if (!requirePositive) {
    // Free model / free tier — zero cost is expected and fine.
    costMicros = 0;
  } else {
    // Paid model but OpenRouter omitted or zeroed the cost. Charge from the
    // catalog price so the call is still billed and the model never blocks.
    const billable = paidMeteringTokenFloors(promptTokens, completionTokens);
    const fallback = modelPriceMicros(
      model,
      billable.promptTokens,
      billable.completionTokens,
    );
    if (fallback !== null) {
      costMicros = fallback;
      console.warn(
        `[metering] ${path}: ${model} missing upstream cost — charged catalog fallback ${fallback}µ ` +
          `(${billable.promptTokens}/${billable.completionTokens} tok)`,
      );
    } else {
      costMicros = unknownPaidModelPriceMicros(
        billable.promptTokens,
        billable.completionTokens,
      );
      warmModelCatalog();
      recordMeteringAlert(
        model,
        path,
        "missing_paid_model_price",
        `${billable.promptTokens}/${billable.completionTokens} tok charged ${costMicros}µ conservative fallback`,
      );
      console.warn(
        `[metering] ${path}: ${model} missing upstream cost and no catalog price — charged conservative fallback ` +
          `${costMicros}µ (${billable.promptTokens}/${billable.completionTokens} tok)`,
      );
    }
  }

  recordUsage(userId, model, promptTokens, completionTokens, costMicros);
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
    headers: openRouterKey()
      ? { Authorization: `Bearer ${openRouterKey()}` }
      : {},
  });
  if (!res.ok) throw new Error(`OpenRouter /models failed: ${res.status}`);
  const payload = (await res.json()) as { data?: ModelEntry[] };
  const data = Array.isArray(payload.data)
    ? payload.data.filter(isTextOutputModel)
    : [];
  globalThis.__olpModelCache = { at: Date.now(), data };
  return data;
}

const KNOWN_UNSAFE_CHAT_MODEL_IDS = new Set([
  // OpenRouter pseudo/limited-access entries that are not callable as normal chat.
  "openrouter/fusion",
  "~anthropic/claude-fable-latest",
  "anthropic/claude-fable-5",
  "allenai/olmo-3-32b-think",
  "arcee-ai/virtuoso-large",
  "arcee-ai/coder-large",
  "openai/gpt-4-turbo-preview",
  "openai/o3-deep-research",
  "openai/o4-mini-deep-research",
  "relace/relace-apply-3",

  // Timed out or quota/rate-limit blocked during live portal smoke testing.
  "nvidia/nemotron-3-ultra-550b-a55b:free",
  "google/gemma-4-26b-a4b-it:free",
  "google/gemma-4-31b-it:free",
  "qwen/qwen3-vl-32b-instruct",
  "qwen/qwen3-next-80b-a3b-instruct:free",
  "openai/gpt-oss-20b:free",
  "qwen/qwen3-coder:free",
  "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",
  "qwen/qwen3-30b-a3b",
  "rekaai/reka-flash-3",
  "meta-llama/llama-3.3-70b-instruct:free",
  "meta-llama/llama-3.2-3b-instruct:free",
  "nousresearch/hermes-3-llama-3.1-405b:free",
]);

export function isTextOutputModel(model: ModelEntry): boolean {
  if (KNOWN_UNSAFE_CHAT_MODEL_IDS.has(model.id)) return false;
  const output =
    model.architecture && typeof model.architecture === "object"
      ? (model.architecture as { output_modalities?: unknown })
          .output_modalities
      : undefined;
  return (
    !Array.isArray(output) || (output.length === 1 && output[0] === "text")
  );
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
    lineBuf = final ? "" : (lines.pop() ?? "");
    for (const line of lines) {
      const data = line.startsWith("data:") ? line.slice(5).trim() : "";
      if (!data || data === "[DONE]") continue;
      try {
        const obj = JSON.parse(data) as {
          usage?: UpstreamUsage;
          model?: string;
        };
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
