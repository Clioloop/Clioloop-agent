import { NextResponse } from "next/server";
import { withUser } from "@/lib/handlers";
import { isMockBilling, portalBaseUrl, stripe } from "@/lib/billing";

export const runtime = "nodejs";

/** Open the Stripe customer billing portal (invoices, card, cancel). */
export const POST = withUser(async (_req, user) => {
  const base = portalBaseUrl();
  if (isMockBilling() || !user.stripe_customer_id) {
    return NextResponse.json({ url: `${base}/pricing`, mock: true });
  }
  const session = await stripe().billingPortal.sessions.create({
    customer: user.stripe_customer_id,
    return_url: `${base}/dashboard`,
  });
  return NextResponse.json({ url: session.url });
});
