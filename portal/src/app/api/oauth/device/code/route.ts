import { NextRequest, NextResponse } from "next/server";
import crypto from "node:crypto";
import { getDb, now } from "@/lib/db";
import { generateUserCode } from "@/lib/tokens";
import { portalBaseUrl } from "@/lib/billing";
import { rateLimitResponse } from "@/lib/ratelimit";

export const runtime = "nodejs";

const DEVICE_CODE_TTL_SECONDS = 900;

/**
 * RFC 8628 device-authorization endpoint.
 * The Clioloop CLI posts form data {client_id, scope?} and expects:
 * device_code, user_code, verification_uri, verification_uri_complete,
 * expires_in, interval.
 */
export async function POST(req: NextRequest) {
  const limited = rateLimitResponse("device_code", req);
  if (limited) return limited;

  const form = await req.formData().catch(() => null);
  const clientId = String(form?.get("client_id") ?? "").trim();
  const scope = String(form?.get("scope") ?? "").trim();
  if (!clientId) {
    return NextResponse.json(
      { error: "invalid_request", error_description: "client_id is required" },
      { status: 400 },
    );
  }

  const db = getDb();
  const deviceCode = crypto.randomBytes(32).toString("base64url");
  let userCode = generateUserCode();
  // user_code is UNIQUE — regenerate on the (astronomically rare) collision.
  for (let i = 0; i < 5; i++) {
    const exists = db
      .prepare("SELECT 1 FROM device_codes WHERE user_code = ?")
      .get(userCode);
    if (!exists) break;
    userCode = generateUserCode();
  }

  const ts = now();
  db.prepare(
    `INSERT INTO device_codes (device_code, user_code, client_id, scope, status, created_at, expires_at, poll_interval)
     VALUES (?, ?, ?, ?, 'pending', ?, ?, 1)`,
  ).run(deviceCode, userCode, clientId, scope, ts, ts + DEVICE_CODE_TTL_SECONDS);

  // Opportunistic cleanup of long-expired grants.
  db.prepare("DELETE FROM device_codes WHERE expires_at < ?").run(ts - 86400);

  const base = portalBaseUrl();
  return NextResponse.json({
    device_code: deviceCode,
    user_code: userCode,
    verification_uri: `${base}/activate`,
    verification_uri_complete: `${base}/activate?code=${encodeURIComponent(userCode)}`,
    expires_in: DEVICE_CODE_TTL_SECONDS,
    interval: 1,
  });
}
