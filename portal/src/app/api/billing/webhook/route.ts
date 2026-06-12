import { NextRequest, NextResponse } from "next/server";
import Stripe from "stripe";
import { applyCheckoutSession, applySubscriptionEvent, isMockBilling, stripe } from "@/lib/billing";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  if (isMockBilling()) return NextResponse.json({ ok: true, mock: true });

  const secret = process.env.STRIPE_WEBHOOK_SECRET?.trim();
  const signature = req.headers.get("stripe-signature");
  const payload = await req.text();

  let event: Stripe.Event;
  try {
    if (!secret || !signature) throw new Error("missing webhook secret or signature");
    event = stripe().webhooks.constructEvent(payload, signature, secret);
  } catch (err) {
    console.error("[portal] webhook signature verification failed:", err);
    return NextResponse.json({ error: "invalid_signature" }, { status: 400 });
  }

  switch (event.type) {
    case "checkout.session.completed":
      applyCheckoutSession(event.data.object);
      break;
    case "customer.subscription.created":
    case "customer.subscription.updated":
    case "customer.subscription.deleted":
      applySubscriptionEvent(event.data.object);
      break;
    default:
      break; // unhandled event types are fine
  }
  return NextResponse.json({ received: true });
}
