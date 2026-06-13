import { NextRequest, NextResponse } from "next/server";

// ─── Rate limiting ───────────────────────────────────────────────────────────
// In-memory sliding window. The portal is a single long-lived process behind
// Caddy, so process-local state is correct here; if it ever scales out, swap
// the Map for Redis without touching call sites.

interface Bucket {
  /** Request timestamps (ms) within the window. */
  hits: number[];
}

declare global {
  var __olpRate: Map<string, Bucket> | undefined;
}

const store = (globalThis.__olpRate ??= new Map<string, Bucket>());

/** Limits per named action: [max requests, window seconds]. */
const LIMITS: Record<string, [number, number]> = {
  login: [10, 15 * 60],
  signup: [5, 60 * 60],
  forgot: [5, 60 * 60],
  reset: [10, 60 * 60],
  verify_request: [5, 60 * 60],
  device_code: [15, 15 * 60],
  oauth_token: [240, 60], // CLI polls every ~1s during device login
  device_approve: [30, 60 * 60],
  checkout: [20, 60 * 60],
  gateway: [120, 60], // per user, agent tool traffic
  inference: [300, 60], // per user
};

/**
 * Client IP: Caddy is the only ingress and always sets X-Forwarded-For,
 * so the first hop in that list is trustworthy.
 */
export function clientIp(req: NextRequest): string {
  const xff = req.headers.get("x-forwarded-for");
  if (xff) return xff.split(",")[0].trim();
  return req.headers.get("x-real-ip") ?? "local";
}

/**
 * Returns null when allowed, or seconds-until-retry when limited.
 * `key` should be the client IP or a user id.
 */
export function rateLimit(action: keyof typeof LIMITS, key: string): number | null {
  const [max, windowSec] = LIMITS[action];
  const nowMs = Date.now();
  const cutoff = nowMs - windowSec * 1000;
  const id = `${action}:${key}`;
  const bucket = store.get(id) ?? { hits: [] };
  bucket.hits = bucket.hits.filter((t) => t > cutoff);
  if (bucket.hits.length >= max) {
    store.set(id, bucket);
    return Math.ceil((bucket.hits[0] + windowSec * 1000 - nowMs) / 1000);
  }
  bucket.hits.push(nowMs);
  store.set(id, bucket);
  // Opportunistic GC so the map doesn't grow unbounded.
  if (store.size > 50_000) {
    for (const [k, b] of store) {
      if (b.hits.every((t) => t <= cutoff)) store.delete(k);
    }
  }
  return null;
}

/** Convenience guard for route handlers: returns a 429 response or null. */
export function rateLimitResponse(
  action: keyof typeof LIMITS,
  req: NextRequest,
  key?: string,
): NextResponse | null {
  const retry = rateLimit(action, key ?? clientIp(req));
  if (retry === null) return null;
  return NextResponse.json(
    {
      error: "rate_limited",
      message: `Too many requests — try again in ${retry}s.`,
      retry_after: retry,
    },
    { status: 429, headers: { "Retry-After": String(retry) } },
  );
}
