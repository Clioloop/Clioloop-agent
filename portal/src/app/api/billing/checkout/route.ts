import { NextRequest, NextResponse } from "next/server";
import { withUser } from "@/lib/handlers";
import { startCheckout } from "@/lib/billing";
import { PLANS, PlanId } from "@/lib/plans";

export const runtime = "nodejs";

export const POST = withUser(async (req: NextRequest, user) => {
  if (!user.email_verified) {
    return NextResponse.json(
      { error: "Verify your email before changing plans — check your inbox or resend from the dashboard." },
      { status: 403 },
    );
  }

  const body = (await req.json().catch(() => null)) as { plan?: string } | null;
  const planId = body?.plan as PlanId;
  if (!planId || !PLANS[planId]) {
    return NextResponse.json({ error: "Unknown plan." }, { status: 400 });
  }

  try {
    const result = await startCheckout(user, planId);
    return NextResponse.json(result);
  } catch (err) {
    console.error("[portal] checkout failed:", err);
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Checkout failed." },
      { status: 500 },
    );
  }
}, { rateLimit: "checkout" });
