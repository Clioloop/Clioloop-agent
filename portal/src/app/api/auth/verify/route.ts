import { NextRequest, NextResponse } from "next/server";
import { getDb } from "@/lib/db";
import { withUser } from "@/lib/handlers";
import { consumeActionToken, sendVerificationEmail } from "@/lib/email";
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
export const POST = withUser(async (_req, user) => {
  if (user.email_verified) {
    return NextResponse.json({ ok: true, already_verified: true });
  }
  await sendVerificationEmail(user);
  return NextResponse.json({ ok: true });
}, { rateLimit: "verify_request" });
