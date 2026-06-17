import { NextRequest, NextResponse } from "next/server";
import bcrypt from "bcryptjs";
import crypto from "node:crypto";
import { getDb, getUserByEmail, getUserById, now, setSubscription } from "@/lib/db";
import { createSession } from "@/lib/session";
import { sendVerificationEmail } from "@/lib/email";
import { rateLimitResponse } from "@/lib/ratelimit";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const limited = rateLimitResponse("signup", req);
  if (limited) return limited;

  const body = (await req.json().catch(() => null)) as
    | { email?: string; password?: string; name?: string }
    | null;
  const email = (body?.email ?? "").trim().toLowerCase();
  const password = body?.password ?? "";
  const name = (body?.name ?? "").trim().slice(0, 80);

  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || email.length > 254) {
    return NextResponse.json({ error: "Enter a valid email address." }, { status: 400 });
  }
  if (password.length < 8 || password.length > 128) {
    return NextResponse.json({ error: "Password must be 8–128 characters." }, { status: 400 });
  }
  if (getUserByEmail(email)) {
    return NextResponse.json({ error: "An account with this email already exists." }, { status: 409 });
  }

  const id = crypto.randomUUID();
  getDb()
    .prepare(
      "INSERT INTO users (id, email, password_hash, name, email_verified, created_at) VALUES (?, ?, ?, ?, 0, ?)",
    )
    .run(id, email, bcrypt.hashSync(password, 12), name, now());
  setSubscription(id, "free", { status: "active" });

  // Best-effort: a failed send must not block account creation — the
  // dashboard has a resend button.
  try {
    await sendVerificationEmail(getUserById(id)!);
  } catch (err) {
    console.error("verification email failed:", err);
  }

  await createSession(id);
  return NextResponse.json({ ok: true });
}
