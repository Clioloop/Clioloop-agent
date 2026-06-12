import { NextRequest, NextResponse } from "next/server";
import { getUserByEmail } from "@/lib/db";
import { sendPasswordResetEmail } from "@/lib/email";
import { rateLimitResponse } from "@/lib/ratelimit";

export const runtime = "nodejs";

/**
 * Request a password reset. Always answers 200 with the same body so the
 * endpoint can't be used to enumerate which emails have accounts.
 */
export async function POST(req: NextRequest) {
  const limited = rateLimitResponse("forgot", req);
  if (limited) return limited;

  const body = (await req.json().catch(() => null)) as { email?: string } | null;
  const email = (body?.email ?? "").trim().toLowerCase();

  const user = email ? getUserByEmail(email) : undefined;
  if (user && !user.banned) {
    try {
      await sendPasswordResetEmail(user);
    } catch (err) {
      console.error("reset email failed:", err);
    }
  }
  return NextResponse.json({
    ok: true,
    message: "If that address has an account, a reset link is on its way.",
  });
}
