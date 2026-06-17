import { NextRequest, NextResponse } from "next/server";
import { getSessionUser } from "@/lib/session";
import { startCheckout } from "@/lib/billing";
import { PLANS, PlanId } from "@/lib/plans";
import { rateLimitResponse } from "@/lib/ratelimit";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const limited = rateLimitResponse("checkout", req);
  if (limited) return limited;

  const user = await getSessionUser();
  if (!user) return NextResponse.json({ error: "not_authenticated" }, { status: 401 });
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
}
