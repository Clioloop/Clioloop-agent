import { getSubscription, recordUsage, currentMonth, monthUsageMicros, UserRow } from "./db";
import { getPlan, ServiceKey } from "./plans";

// ─── Tool gateway ────────────────────────────────────────────────────────────
// Vendor passthrough proxies for the bundled agent services. The Clioloop
// agent's managed-tool plumbing (tools/managed_tool_gateway.py) authenticates
// with the subscriber's OAuth access token and expects each vendor's native
// API surface at `{portal}/api/gateway/{vendor}` — the portal swaps the
// subscriber token for the house upstream key and forwards the request.
//
// A vendor is live only when its upstream key is configured, so a fresh
// self-hosted portal degrades gracefully to models-only.

export interface GatewayVendor {
  /** Vendor slug — must match the Clioloop agent's gateway vendor names. */
  id: string;
  /** Native upstream origin the requests are forwarded to. */
  upstream: string;
  /** Env var holding the house API key for this upstream. */
  keyEnv: string;
  /** Optional env var overriding the upstream origin (self-hosted vendors). */
  upstreamEnv: string;
  /** Build the upstream auth headers from the house key. */
  authHeaders: (key: string) => Record<string, string>;
  /** Plan service this vendor is billed under. */
  service: ServiceKey;
  /** Flat per-request metering, in credit micros (1e6 = €1). */
  costMicros: number;
}

export const GATEWAY_VENDORS: Record<string, GatewayVendor> = {
  firecrawl: {
    id: "firecrawl",
    upstream: "https://api.firecrawl.dev",
    keyEnv: "FIRECRAWL_API_KEY",
    upstreamEnv: "FIRECRAWL_UPSTREAM_URL",
    authHeaders: (key) => ({ Authorization: `Bearer ${key}` }),
    service: "web",
    costMicros: 10_000, // ~1c per search/scrape
  },
  "fal-queue": {
    id: "fal-queue",
    upstream: "https://queue.fal.run",
    keyEnv: "FAL_KEY",
    upstreamEnv: "FAL_QUEUE_UPSTREAM_URL",
    authHeaders: (key) => ({ Authorization: `Key ${key}` }),
    service: "video_gen",
    costMicros: 40_000, // ~4c per generation request
  },
  // Premium TTS: a self-hosted Supertonic-3 server speaking the OpenAI
  // /v1/audio/speech dialect (deploy/supertonic_server.py). The vendor id
  // stays "openai-audio" — that's the wire contract the Clioloop agent's
  // gateway client uses — but no OpenAI account is involved.
  "openai-audio": {
    id: "openai-audio",
    upstream: "http://127.0.0.1:8077",
    keyEnv: "OPENAI_API_KEY",
    upstreamEnv: "OPENAI_AUDIO_UPSTREAM_URL",
    authHeaders: (key) =>
      key ? { Authorization: `Bearer ${key}` } : ({} as Record<string, string>),
    service: "tts",
    costMicros: 10_000, // €0.01 per TTS request (self-hosted Supertonic)
  },
  "browser-use": {
    id: "browser-use",
    upstream: "https://api.browser-use.com",
    keyEnv: "BROWSER_USE_API_KEY",
    upstreamEnv: "BROWSER_USE_UPSTREAM_URL",
    authHeaders: (key) => ({ "X-Browser-Use-API-Key": key }),
    service: "browser",
    costMicros: 25_000,
  },
  // Self-hosted image generation: a private server (e.g. a local FLUX box)
  // exposed to the portal via a tunnel. Speaks POST /generate {prompt, steps}
  // with X-API-Key. Set CLIOLOOP_IMAGE_UPSTREAM_URL to the tunnel origin and
  // CLIOLOOP_IMAGE_KEY to the server's API key. When live it replaces the FAL
  // image_gen path for entitled (Pro) subscribers.
  "clioloop-image": {
    id: "clioloop-image",
    upstream: "http://127.0.0.1:8200",
    keyEnv: "CLIOLOOP_IMAGE_KEY",
    upstreamEnv: "CLIOLOOP_IMAGE_UPSTREAM_URL",
    authHeaders: (key) => (key ? { "X-API-Key": key } : ({} as Record<string, string>)),
    service: "image_gen",
    costMicros: 20_000, // €0.02 per image generation (charged on POST /generate only)
  },
};

export function vendorUpstreamKey(vendor: GatewayVendor): string {
  return process.env[vendor.keyEnv]?.trim() ?? "";
}

export function vendorUpstreamOrigin(vendor: GatewayVendor): string {
  return (process.env[vendor.upstreamEnv]?.trim() || vendor.upstream).replace(/\/+$/, "");
}

/**
 * Vendor is configured server-side: a house key, or an explicit upstream
 * override (self-hosted upstreams like the Supertonic TTS server need none).
 */
export function vendorConfigured(vendor: GatewayVendor): boolean {
  return !!vendorUpstreamKey(vendor) || !!process.env[vendor.upstreamEnv]?.trim();
}

/** Service entitlements for an account: plan grant ∧ vendor configured. */
export function serviceAvailability(userId: string): Record<ServiceKey, boolean> {
  const plan = getPlan(getSubscription(userId)?.plan);
  const configuredServices = new Set(
    Object.values(GATEWAY_VENDORS)
      .filter(vendorConfigured)
      .map((v) => v.service),
  );
  const services: ServiceKey[] = ["web", "browser", "image_gen", "video_gen", "tts"];
  return Object.fromEntries(
    services.map((s) => [s, plan.services.includes(s) && configuredServices.has(s)]),
  ) as Record<ServiceKey, boolean>;
}

/** Per-request metering. Some vendors serve generated assets after the paid generation call. */
export function gatewayRequestCostMicros(
  vendor: GatewayVendor,
  method: string,
  path: string[] = [],
): number {
  if (vendor.id === "clioloop-image") {
    return method.toUpperCase() === "POST" && path[0] === "generate" ? vendor.costMicros : 0;
  }
  return vendor.costMicros;
}

export interface GatewayDenial {
  status: number;
  error: string;
  message: string;
}

/** Entitlement gate for a gateway call — mirrors the inference proxy's. */
export function checkGatewayEntitlement(
  user: UserRow,
  vendor: GatewayVendor,
  costMicros = vendor.costMicros,
): GatewayDenial | null {
  if (!vendorConfigured(vendor)) {
    return {
      status: 503,
      error: "vendor_not_configured",
      message: `The ${vendor.id} gateway is not configured on this portal.`,
    };
  }
  const sub = getSubscription(user.id);
  const plan = getPlan(sub?.plan);
  if (!plan.services.includes(vendor.service)) {
    return {
      status: 403,
      error: "plan_upgrade_required",
      message: `${vendor.service} is not included in the ${plan.name} plan — upgrade at the Omni Loop Portal.`,
    };
  }
  if (plan.requiresCardVerification && !user.card_verified) {
    return {
      status: 403,
      error: "card_verification_required",
      message: "Verify a card in the Omni Loop Portal dashboard to use gateway services.",
    };
  }
  const used = monthUsageMicros(user.id);
  if (costMicros > 0 && used + costMicros > plan.monthlyCreditsMicros) {
    return {
      status: 429,
      error: "monthly_limit_reached",
      message: `Monthly allowance reached for ${currentMonth()} — upgrade your plan or wait for the reset.`,
    };
  }
  return null;
}

/** Meter one gateway call against the subscriber's monthly allowance. */
export function recordGatewayUsage(
  userId: string,
  vendor: GatewayVendor,
  costMicros = vendor.costMicros,
): void {
  if (costMicros <= 0) return;
  recordUsage(userId, `gateway:${vendor.id}`, 0, 0, costMicros);
}
