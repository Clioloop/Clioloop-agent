import { NextRequest, NextResponse } from "next/server";
import { getSubscription, monthUsageMicros, currentMonth } from "@/lib/db";
import { withBearer } from "@/lib/handlers";
import { getPlan, planAllowsFusion } from "@/lib/plans";
import { portalBaseUrl } from "@/lib/billing";
import { GATEWAY_VENDORS, serviceAvailability, vendorConfigured } from "@/lib/gateway";

export const runtime = "nodejs";

/**
 * Bearer-token account info, consumed by the Clioloop CLI
 * (clio_cli/portal_account.py and clio_cli/portal_subscription.py)
 * to show plan / entitlement / tool-gateway status.
 */
export const GET = withBearer(async (req: NextRequest, identity) => {
  const { user } = identity;
  const sub = getSubscription(user.id);
  const plan = getPlan(sub?.plan);
  const base = portalBaseUrl();

  // Tool-gateway entitlements: plan grant ∧ vendor configured server-side.
  // Consumed by clio_cli/portal_subscription.py to light up the managed
  // web / browser / image / video / TTS tool rows.
  const features = serviceAvailability(user.id);
  const gatewayVendors = Object.values(GATEWAY_VENDORS)
    .filter((v) => vendorConfigured(v) && plan.services.includes(v.service))
    .map((v) => v.id);

  return NextResponse.json({
    logged_in: true,
    email: user.email,
    name: user.name,
    plan: plan.id,
    plan_name: plan.name,
    is_free_tier: plan.id === "free",
    paid_service_access: plan.id !== "free",
    card_verified: !!user.card_verified,
    status: sub?.status ?? "active",
    inference_base_url: `${base}/api/v1`,
    portal_url: base,
    features: { ...features, fusion: planAllowsFusion(plan.id) },
    tool_gateway: {
      entitled: gatewayVendors.length > 0,
      base_url: `${base}/api/gateway`,
      vendors: gatewayVendors,
      // vidu-video rides the vidu vendor but is a separate entitlement
      // (Max tiers only) — clio_cli checks tool_gateway_entitled_for("vidu-video").
      entitlements: [
        ...gatewayVendors,
        ...(features.video_gen ? ["vidu-video"] : []),
        ...(features.music_gen ? ["clioloop-music"] : []),
      ],
    },
    usage: {
      month: currentMonth(),
      used_micros: monthUsageMicros(user.id),
      limit_micros: plan.monthlyCreditsMicros,
    },
  });
}, {
  unauthorized: () =>
    NextResponse.json({ logged_in: false, error: "invalid_token" }, { status: 401 }),
});
