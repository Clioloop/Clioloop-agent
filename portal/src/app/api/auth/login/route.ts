import { NextRequest, NextResponse } from "next/server";
import bcrypt from "bcryptjs";
import { getUserByEmail } from "@/lib/db";
import { createSession } from "@/lib/session";
import { rateLimitResponse } from "@/lib/ratelimit";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const limited = rateLimitResponse("login", req);
  if (limited) return limited;

  const body = (await req.json().catch(() => null)) as
    | { email?: string; password?: string }
    | null;
  const email = (body?.email ?? "").trim().toLowerCase();
  const password = body?.password ?? "";

  const user = getUserByEmail(email);
  // Constant-shape comparison: always run bcrypt so missing accounts take
  // the same time as wrong passwords.
  const hash =
    user?.password_hash ??
    "$2a$12$C6UzMDM.H6dfI/f/IKcEeO5g1u8N1JmO4vBibFDb6JF0EIa4WfO5y";
  const ok = bcrypt.compareSync(password, hash);
  if (!user || !ok) {
    return NextResponse.json({ error: "Invalid email or password." }, { status: 401 });
  }
  if (user.banned) {
    return NextResponse.json({ error: "This account is suspended." }, { status: 403 });
  }
  await createSession(user.id);
  return NextResponse.json({ ok: true });
}
