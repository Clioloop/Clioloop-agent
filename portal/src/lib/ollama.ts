import { fetchModels } from "./openrouter";
import type { PlanId } from "./plans";

// ─── Ollama Cloud upstream ───────────────────────────────────────────────────
// Second inference upstream behind the portal. Flat-rate subscription key, so
// there is NO per-request cost from the wire — we assign each model the cost of
// its closest OpenRouter sibling and meter against the plan allowance. Free +
// Pro traffic stays on this key; only Max may also spend on OpenRouter.
//
// User-facing copy must never say "Ollama": the provider label stays
// "Omni Loop Portal" and only plain model names (kimi-k2.7-code, …) are shown.

export const OLLAMA_BASE =
  process.env.OLLAMA_UPSTREAM_URL?.trim() || "https://ollama.com/v1";

export function ollamaKey(): string {
  return process.env.OLLAMA_API_KEY?.trim() ?? "";
}

/** The one model that is free for EVERY tier (first N requests/day per user). */
export const FREE_OLLAMA_MODEL = "kimi-k2.7-code";

/** Shared daily free-model allotment, per user (UTC day). Beyond it: free tier
 *  is blocked; pro/max keep using the free model but charged at its rate. */
export const FREE_DAILY_REQUEST_CAP = 500;

/**
 * Route/classify by id shape: OpenRouter ids are always `vendor/model`; every
 * Ollama Cloud id is bare (uses `:tag`, never `/`). So a slash-free id is an
 * Ollama model. This needs no catalog fetch, so it can't break on a fetch hiccup.
 */
export function isOllamaModel(id: string): boolean {
  return id.length > 0 && !id.includes("/");
}

/** Plan model-access policy (replaces the old freeModelsOnly-only check). */
export function modelAllowedForPlan(planId: PlanId, modelId: string): boolean {
  if (planId === "free") return modelId === FREE_OLLAMA_MODEL;
  if (planId === "pro") return isOllamaModel(modelId);
  return true; // max / max20x: any Ollama or OpenRouter model
}

// ─── Pricing (mirror the OpenRouter equivalent) ──────────────────────────────
// Each Ollama model is priced at its closest OpenRouter sibling's LIVE price
// (so prices track OpenRouter automatically). The free model has no sibling for
// the in-allotment case (cost 0); its mapping below is only used for the
// pro/max >cap overage charge.
const OLLAMA_TO_OPENROUTER: Record<string, string> = {
  "kimi-k2:1t": "moonshotai/kimi-k2",
  "kimi-k2-thinking": "moonshotai/kimi-k2-thinking",
  "kimi-k2.5": "moonshotai/kimi-k2.5",
  "kimi-k2.6": "moonshotai/kimi-k2.5",
  "kimi-k2.7-code": "moonshotai/kimi-k2.5", // overage price for the free model only
  "qwen3-coder:480b": "qwen/qwen3-coder",
  "qwen3-coder-next": "qwen/qwen3-coder-next",
  "qwen3-next:80b": "qwen/qwen3-next-80b-a3b-instruct",
  "qwen3-vl:235b": "qwen/qwen3-vl-235b-a22b-instruct",
  "qwen3-vl:235b-instruct": "qwen/qwen3-vl-235b-a22b-instruct",
  "qwen3.5:397b": "qwen/qwen3-coder",
  "deepseek-v3.1:671b": "deepseek/deepseek-chat-v3.1",
  "deepseek-v3.2": "deepseek/deepseek-v3.2",
  "deepseek-v4-flash": "deepseek/deepseek-v3.2",
  "deepseek-v4-pro": "deepseek/deepseek-chat-v3.1",
  "gpt-oss:120b": "openai/gpt-oss-120b",
  "gpt-oss:20b": "openai/gpt-oss-20b",
  "glm-4.6": "z-ai/glm-4.6",
  "glm-4.7": "z-ai/glm-4.6",
  "glm-5": "z-ai/glm-4.6",
  "glm-5.1": "z-ai/glm-4.6",
  "gemma3:4b": "google/gemma-3-4b-it",
  "gemma3:12b": "google/gemma-3-12b-it",
  "gemma3:27b": "google/gemma-3-27b-it",
  "gemma4:31b": "google/gemma-3-27b-it",
  "minimax-m2": "minimax/minimax-m2",
  "minimax-m2.1": "minimax/minimax-m2",
  "minimax-m2.5": "minimax/minimax-m2",
  "minimax-m2.7": "minimax/minimax-m2",
  "minimax-m3": "minimax/minimax-m2",
  "ministral-3:3b": "mistralai/ministral-3b-2512",
  "ministral-3:8b": "mistralai/ministral-8b-2512",
  "ministral-3:14b": "mistralai/ministral-14b-2512",
  "mistral-large-3:675b": "mistralai/mistral-large-2512",
  "devstral-2:123b": "mistralai/devstral-2512",
  "devstral-small-2:24b": "mistralai/devstral-2512",
  "cogito-2.1:671b": "deepcogito/cogito-v2.1-671b",
  "nemotron-3-nano:30b": "nvidia/nemotron-3-nano-30b-a3b",
  "nemotron-3-super": "nvidia/nemotron-3-super-120b-a12b",
  "nemotron-3-ultra": "nvidia/nemotron-3-super-120b-a12b",
};

/** $/token used when neither the map nor live OpenRouter pricing resolves. */
const DEFAULT_OLLAMA_PRICE: TokenPrice = { prompt: 0.0000003, completion: 0.0000012 };

export interface TokenPrice {
  prompt: number; // USD per token
  completion: number; // USD per token
}

/** Resolve an Ollama model's per-token price from its OpenRouter sibling's live pricing. */
export async function ollamaPricing(id: string): Promise<TokenPrice> {
  const orId = OLLAMA_TO_OPENROUTER[id];
  if (orId) {
    try {
      const models = await fetchModels();
      const p = models.find((m) => m.id === orId)?.pricing;
      if (p) {
        const prompt = Number.parseFloat(String(p.prompt ?? ""));
        const completion = Number.parseFloat(String(p.completion ?? ""));
        if (Number.isFinite(prompt) && Number.isFinite(completion)) {
          return { prompt, completion };
        }
      }
    } catch {
      // fall through to default
    }
  }
  return DEFAULT_OLLAMA_PRICE;
}

/** Cost in micros for an Ollama call given a resolved price. Pass a zero price
 *  ({prompt:0,completion:0}) for the in-allotment free model so it records €0. */
export function ollamaCostMicros(
  usage: { prompt_tokens?: number; completion_tokens?: number } | undefined,
  price: TokenPrice,
): number {
  if (!usage) return 0;
  const cost =
    (usage.prompt_tokens ?? 0) * price.prompt +
    (usage.completion_tokens ?? 0) * price.completion;
  return Math.max(0, Math.round(cost * 1_000_000));
}

// ─── Catalog (cached) ────────────────────────────────────────────────────────
interface OllamaModelEntry {
  id: string;
  [k: string]: unknown;
}

interface CatalogEntry {
  id: string;
  name: string;
  /** OpenRouter-style string pricing so the CLI's pricing parser + free
   *  detection work unchanged. Free model → "0"/"0". */
  pricing: { prompt: string; completion: string };
}

declare global {
  // eslint-disable-next-line no-var
  var __olpOllamaCache: { at: number; ids: string[] } | undefined;
}
const OLLAMA_CACHE_TTL_MS = 5 * 60 * 1000;

/** Live Ollama Cloud model ids (cached 5 min). Empty on failure. */
export async function fetchOllamaModels(): Promise<string[]> {
  const cache = globalThis.__olpOllamaCache;
  if (cache && Date.now() - cache.at < OLLAMA_CACHE_TTL_MS) return cache.ids;
  const key = ollamaKey();
  if (!key) return [];
  const res = await fetch(`${OLLAMA_BASE}/models`, {
    headers: { Authorization: `Bearer ${key}` },
  });
  if (!res.ok) throw new Error(`Ollama /models failed: ${res.status}`);
  const payload = (await res.json()) as { data?: OllamaModelEntry[] };
  const ids = Array.isArray(payload.data)
    ? payload.data.map((m) => m.id).filter((x): x is string => !!x)
    : [];
  globalThis.__olpOllamaCache = { at: Date.now(), ids };
  return ids;
}

/** Ollama catalog entries with injected pricing for `/api/v1/models`. The free
 *  model is priced "0"/"0" (it IS the free model; the >cap overage charge is a
 *  runtime fair-use behavior, not advertised in the catalog). */
export async function ollamaCatalogEntries(): Promise<CatalogEntry[]> {
  const ids = await fetchOllamaModels();
  const out: CatalogEntry[] = [];
  for (const id of ids) {
    if (id === FREE_OLLAMA_MODEL) {
      out.push({ id, name: id, pricing: { prompt: "0", completion: "0" } });
      continue;
    }
    const p = await ollamaPricing(id);
    out.push({
      id,
      name: id,
      pricing: { prompt: String(p.prompt), completion: String(p.completion) },
    });
  }
  return out;
}
