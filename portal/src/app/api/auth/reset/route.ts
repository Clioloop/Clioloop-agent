import { NextRequest, NextResponse } from "next/server";
import bcrypt from "bcryptjs";
import { getDb } from "@/lib/db";
import { consumeActionToken } from "@/lib/email";
import { rateLimitResponse } from "@/lib/ratelimit";

export const runtime = "nodejs";

/** Complete a password reset with a token from the email link. */
export async function POST(req: NextRequest) {
  const limited = rateLimitResponse("reset", req);
  if (limited) return limited;

  const body = (await req.json().catch(() => null)) as
    | { token?: string; password?: string }
    | null;
  const token = body?.token ?? "";
  const password = body?.password ?? "";

  if (password.length < 8 || password.length > 128) {
    return NextResponse.json({ error: "Password must be 8–128 characters." }, { status: 400 });
  }
  const userId = token ? consumeActionToken(token, "reset") : null;
  if (!userId) {
    return NextResponse.json(
      { error: "This reset link is invalid or has expired — request a new one." },
      { status: 400 },
    );
  }

  const db = getDb();
  db.prepare("UPDATE users SET password_hash = ? WHERE id = ?").run(
    bcrypt.hashSync(password, 12),
    userId,
  );
  // A reset proves control of the inbox — count it as verification, and cut
  // off every connected device in case the account was compromised.
  db.prepare("UPDATE users SET email_verified = 1 WHERE id = ?").run(userId);
  db.prepare("UPDATE oauth_tokens SET revoked = 1 WHERE user_id = ?").run(userId);

  return NextResponse.json({ ok: true });
}
