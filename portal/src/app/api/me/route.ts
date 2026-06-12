import { NextResponse } from "next/server";
import { getDb, getSubscription, monthUsageMicros, currentMonth } from "@/lib/db";
import { getSessionUser } from "@/lib/session";
import { getPlan } from "@/lib/plans";
import { isMockBilling } from "@/lib/billing";
import { serviceAvailability } from "@/lib/gateway";

export const runtime = "nodejs";

/** Session-based account snapshot for the web dashboard. */
export async function GET() {
  const user = await getSessionUser();
  if (!user) return NextResponse.json({ error: "not_authenticated" }, { status: 401 });

  const sub = getSubscription(user.id);
  const plan = getPlan(sub?.plan);
  const devices = getDb()
    .prepare(
      `SELECT COUNT(DISTINCT family_id) AS n FROM oauth_tokens
       WHERE user_id = ? AND kind = 'refresh' AND revoked = 0`,
    )
    .get(user.id) as { n: number };

  return NextResponse.json({
    user: {
      id: user.id,
      email: user.email,
      name: user.name,
      card_verified: !!user.card_verified,
      email_verified: !!user.email_verified,
    },
    plan: {
      id: plan.id,
      name: plan.name,
      price_eur: plan.priceEur,
      status: sub?.status ?? "active",
      renews_at: sub?.renews_at ?? null,
      free_models_only: plan.freeModelsOnly,
    },
    usage: {
      month: currentMonth(),
      used_micros: monthUsageMicros(user.id),
      limit_micros: plan.monthlyCreditsMicros,
    },
    services: serviceAvailability(user.id),
    connected_devices: devices.n,
    mock_billing: isMockBilling(),
  });
}
