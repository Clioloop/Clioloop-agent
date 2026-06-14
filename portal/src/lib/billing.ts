import Stripe from "stripe";
import { getDb, getUserById, now, setSubscription, UserRow } from "./db";
import { getPlan, PlanId, PLANS } from "./plans";

// When STRIPE_SECRET_KEY is missing the portal runs in MOCK billing mode:
// plan changes apply instantly without payment. This keeps local development
// and self-hosted evaluation one-command simple.
export function isMockBilling(): boolean {
  return !process.env.STRIPE_SECRET_KEY?.trim();
}

let _stripe: Stripe | null = null;
export function stripe(): Stripe {
  if (!_stripe) {
    _stripe = new Stripe(process.env.STRIPE_SECRET_KEY!.trim());
  }
  return _stripe;
}

export function portalBaseUrl(): string {
  return (process.env.PORTAL_BASE_URL?.trim() || "http://localhost:4280").replace(/\/+$/, "");
}

async function ensureStripeCustomer(user: UserRow): Promise<string> {
  if (user.stripe_customer_id) return user.stripe_customer_id;
  const customer = await stripe().customers.create({
    email: user.email,
    name: user.name || undefined,
    metadata: { olp_user_id: user.id },
  });
  getDb()
    .prepare("UPDATE users SET stripe_customer_id = ? WHERE id = ?")
    .run(customer.id, user.id);
  return customer.id;
}

export interface CheckoutResult {
  url: string;
  mock: boolean;
}

/**
 * Start a plan change.
 *  - free  → Stripe Checkout in `setup` mode (card verification, no charge)
 *  - paid  → Stripe Checkout subscription for the plan's recurring price
 *  - mock  → apply immediately and bounce back to the dashboard
 */
export async function startCheckout(user: UserRow, planId: PlanId): Promise<CheckoutResult> {
  const plan = getPlan(planId);
  const base = portalBaseUrl();

  if (isMockBilling()) {
    if (plan.id === "free") {
      getDb().prepare("UPDATE users SET card_verified = 1 WHERE id = ?").run(user.id);
    }
    setSubscription(user.id, plan.id, { status: "active" });
    return { url: `${base}/dashboard?billing=mock`, mock: true };
  }

  const customerId = await ensureStripeCustomer(user);

  if (plan.id === "free") {
    const session = await stripe().checkout.sessions.create({
      mode: "setup",
      customer: customerId,
      success_url: `${base}/api/billing/confirm?session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: `${base}/pricing?cancelled=1`,
      metadata: { olp_user_id: user.id, olp_plan: "free" },
    });
    return { url: session.url!, mock: false };
  }

  const priceId = process.env[plan.stripePriceEnv!]?.trim();
  if (!priceId) {
    throw new Error(
      `Stripe price for plan "${plan.id}" is not configured (set ${plan.stripePriceEnv})`,
    );
  }
  const session = await stripe().checkout.sessions.create({
    mode: "subscription",
    customer: customerId,
    line_items: [{ price: priceId, quantity: 1 }],
    success_url: `${base}/api/billing/confirm?session_id={CHECKOUT_SESSION_ID}`,
    cancel_url: `${base}/pricing?cancelled=1`,
    allow_promotion_codes: true,
    metadata: { olp_user_id: user.id, olp_plan: plan.id },
    subscription_data: { metadata: { olp_user_id: user.id, olp_plan: plan.id } },
  });
  return { url: session.url!, mock: false };
}

/** Apply the outcome of a completed Checkout session (confirm + webhook). */
export function applyCheckoutSession(session: Stripe.Checkout.Session): void {
  const userId = session.metadata?.olp_user_id;
  const planId = (session.metadata?.olp_plan ?? "") as PlanId;
  if (!userId || !getUserById(userId) || !PLANS[planId]) return;

  if (session.mode === "setup") {
    // Free-tier card verification: a payment method is now on file.
    getDb().prepare("UPDATE users SET card_verified = 1 WHERE id = ?").run(userId);
    setSubscription(userId, "free", { status: "active" });
    return;
  }
  if (session.mode === "subscription" && session.status === "complete") {
    setSubscription(userId, planId, {
      status: "active",
      stripe_subscription_id:
        typeof session.subscription === "string"
          ? session.subscription
          : session.subscription?.id ?? null,
    });
    getDb().prepare("UPDATE users SET card_verified = 1 WHERE id = ?").run(userId);
  }
}

/** Keep our subscription table in sync with Stripe subscription lifecycle. */
export function applySubscriptionEvent(sub: Stripe.Subscription): void {
  const userId = sub.metadata?.olp_user_id;
  const planId = (sub.metadata?.olp_plan ?? "") as PlanId;
  if (!userId || !getUserById(userId)) return;

  if (sub.status === "active" || sub.status === "trialing") {
    // Stripe moved current_period_end from the subscription to its items in
    // newer API versions — accept either shape.
    const subAny = sub as unknown as { current_period_end?: number };
    const itemAny = sub.items.data[0] as unknown as { current_period_end?: number } | undefined;
    const renewsAt = subAny.current_period_end ?? itemAny?.current_period_end ?? null;
    setSubscription(userId, PLANS[planId] ? planId : "pro", {
      status: "active",
      stripe_subscription_id: sub.id,
      renews_at: renewsAt,
    });
  } else if (["canceled", "unpaid", "incomplete_expired"].includes(sub.status)) {
    setSubscription(userId, "free", { status: "active", renews_at: null });
  } else if (sub.status === "past_due") {
    const db = getDb();
    db.prepare("UPDATE subscriptions SET status = 'past_due', updated_at = ? WHERE user_id = ?")
      .run(now(), userId);
  }
}
