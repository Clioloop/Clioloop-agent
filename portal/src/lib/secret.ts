import { randomBytes } from "node:crypto";

// Single source of truth for the HMAC secret behind sessions and access-token
// signatures. Production must configure SESSION_SECRET; dev falls back to a
// random per-process secret (sessions won't survive restarts — fine locally).
let devSecret: string | null = null;

export function sessionSecret(): string {
  const env = process.env.SESSION_SECRET?.trim();
  if (env) return env;
  if (process.env.NODE_ENV === "production") {
    throw new Error("SESSION_SECRET must be set in production");
  }
  if (!devSecret) devSecret = randomBytes(32).toString("hex");
  return devSecret;
}

export function sessionSecretBytes(): Uint8Array {
  return new TextEncoder().encode(sessionSecret());
}
