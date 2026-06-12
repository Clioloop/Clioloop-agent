import { NextRequest, NextResponse } from "next/server";
import { getDb } from "@/lib/db";
import { getSessionUser } from "@/lib/session";
import { consumeActionToken, sendVerificationEmail } from "@/lib/email";
import { rateLimitResponse } from "@/lib/ratelimit";
import { portalBaseUrl } from "@/lib/billing";

export const runtime = "nodejs";

/** Email-link landing: consume the verify token and bounce to the dashboard. */
export async function GET(req: NextRequest) {
  const token = req.nextUrl.searchParams.get("token") ?? "";
  const userId = token ? consumeActionToken(token, "verify") : null;
  const base = portalBaseUrl();
  if (!userId) {
    return NextResponse.redirect(`${base}/dashboard?verify=invalid`);
  }
  getDb().prepare("UPDATE users SET email_verified = 1 WHERE id = ?").run(userId);
  return NextResponse.redirect(`${base}/dashboard?verify=ok`);
}

/** Resend the verification email (dashboard button). */
export async function POST(req: NextRequest) {
  const limited = rateLimitResponse("verify_request", req);
  if (limited) return limited;

  const user = await getSessionUser();
  if (!user) {
    return NextResponse.json({ error: "not_authenticated" }, { status: 401 });
  }
  if (user.email_verified) {
    return NextResponse.json({ ok: true, already_verified: true });
  }
  await sendVerificationEmail(user);
  return NextResponse.json({ ok: true });
}
