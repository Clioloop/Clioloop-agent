import { SignJWT, jwtVerify } from "jose";
import { cookies } from "next/headers";
import { getUserById, UserRow } from "./db";
import { sessionSecretBytes } from "./secret";

const COOKIE = "olp_session";
const MAX_AGE_SECONDS = 60 * 60 * 24 * 30;

// SESSION_SECRET is required in production (secret.ts throws otherwise);
// the dev fallback is random per process, so sessions reset on restart.
const secret = sessionSecretBytes;

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
