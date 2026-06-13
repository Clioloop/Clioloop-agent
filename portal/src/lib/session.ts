import { SignJWT, jwtVerify } from "jose";
import { cookies } from "next/headers";
import crypto from "node:crypto";
import { getUserById, UserRow } from "./db";

const COOKIE = "olp_session";
const MAX_AGE_SECONDS = 60 * 60 * 24 * 30;

// In production set SESSION_SECRET; the dev fallback is random per process,
// so sessions reset on restart (harmless locally, loud in prod logs).
declare global {
  var __olpSessionSecret: Uint8Array | undefined;
}

function secret(): Uint8Array {
  const env = process.env.SESSION_SECRET?.trim();
  if (env) return new TextEncoder().encode(env);
  if (!globalThis.__olpSessionSecret) {
    if (process.env.NODE_ENV === "production") {
      console.warn("[portal] SESSION_SECRET is not set — sessions will not survive restarts");
    }
    globalThis.__olpSessionSecret = crypto.randomBytes(32);
  }
  return globalThis.__olpSessionSecret;
}

export async function createSession(userId: string): Promise<void> {
  const jwt = await new SignJWT({ sub: userId })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime(`${MAX_AGE_SECONDS}s`)
    .sign(secret());
  // Key `secure` off the real deployment scheme, not NODE_ENV — a production
  // build served over plain http (local portal, LAN install) must still work.
  const base = process.env.PORTAL_BASE_URL?.trim() || "http://localhost:4280";
  (await cookies()).set(COOKIE, jwt, {
    httpOnly: true,
    sameSite: "lax",
    secure: base.startsWith("https://"),
    maxAge: MAX_AGE_SECONDS,
    path: "/",
  });
}

export async function destroySession(): Promise<void> {
  (await cookies()).delete(COOKIE);
}

export async function getSessionUser(): Promise<UserRow | null> {
  const jwt = (await cookies()).get(COOKIE)?.value;
  if (!jwt) return null;
  try {
    const { payload } = await jwtVerify(jwt, secret());
    if (typeof payload.sub !== "string") return null;
    const user = getUserById(payload.sub) ?? null;
    // Suspended accounts lose their sessions immediately.
    if (user?.banned) return null;
    return user;
  } catch {
    return null;
  }
}
