import { NextRequest, NextResponse } from "next/server";
import { getDb, now } from "@/lib/db";
import { withUser } from "@/lib/handlers";

export const runtime = "nodejs";

/** Browser-side approval of a pending device code (the /activate page). */
export const POST = withUser(async (req: NextRequest, user) => {
  if (!user.email_verified) {
    return NextResponse.json(
      {
        error: "email_unverified",
        message: "Verify your email before connecting devices — check your inbox or resend from the dashboard.",
      },
      { status: 403 },
    );
  }
  const body = (await req.json().catch(() => null)) as
    | { user_code?: string; action?: string }
    | null;
  const userCode = (body?.user_code ?? "").trim().toUpperCase();
  const action = body?.action === "deny" ? "denied" : "approved";
  if (!userCode) {
    return NextResponse.json({ error: "missing_code" }, { status: 400 });
  }

  const db = getDb();
  const row = db
    .prepare("SELECT * FROM device_codes WHERE user_code = ?")
    .get(userCode) as { status: string; expires_at: number } | undefined;

  if (!row) {
    return NextResponse.json(
      { error: "unknown_code", message: "That code doesn't match a pending device login." },
      { status: 404 },
    );
  }
  if (row.expires_at < now()) {
    return NextResponse.json(
      { error: "expired", message: "This code has expired — restart the login on your device." },
      { status: 410 },
    );
  }
  if (row.status !== "pending") {
    return NextResponse.json(
      { error: "already_handled", message: "This code was already used." },
      { status: 409 },
    );
  }

  db.prepare("UPDATE device_codes SET status = ?, user_id = ? WHERE user_code = ?")
    .run(action, user.id, userCode);

  return NextResponse.json({ ok: true, status: action });
}, { rateLimit: "device_approve" });
