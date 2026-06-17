import { NextRequest, NextResponse } from "next/server";
import { applyCheckoutSession, isMockBilling, portalBaseUrl, stripe } from "@/lib/billing";

export const runtime = "nodejs";

/**
 * Checkout success redirect. Applies the session result immediately so the
 * dashboard reflects the new plan even before the webhook arrives (webhooks
 * remain the source of truth for later lifecycle events).
 */
export async function GET(req: NextRequest) {
  const base = portalBaseUrl();
  const sessionId = req.nextUrl.searchParams.get("session_id");
  if (!isMockBilling() && sessionId) {
    try {
      const session = await stripe().checkout.sessions.retrieve(sessionId);
      applyCheckoutSession(session);
    } catch (err) {
      console.error("[portal] checkout confirm failed:", err);
    }
  }
  return NextResponse.redirect(`${base}/dashboard?billing=success`);
}
