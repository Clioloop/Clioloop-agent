import { NextRequest, NextResponse } from "next/server";
import { currentMonth, getDb, now, UserRow } from "@/lib/db";
import { PLANS } from "@/lib/plans";
import { getSessionUser } from "@/lib/session";

export const runtime = "nodejs";

/**
 * Comma-separated list of admin account emails (env ADMIN_EMAILS).
 * Requires a VERIFIED email: registering an admin address you don't
 * control must never grant the panel (verification proves inbox ownership).
 */
function isAdmin(user: UserRow | null): user is UserRow {
  if (!user || !user.email_verified) return false;
  const admins = (process.env.ADMIN_EMAILS ?? "")
    .split(",")
    .map((e) => e.trim().toLowerCase())
    .filter(Boolean);
  return admins.includes(user.email.toLowerCase());
}

/** Account overview for the admin page. */
export async function GET() {
  const me = await getSessionUser();
  if (!isAdmin(me)) return NextResponse.json({ error: "forbidden" }, { status: 403 });

  const db = getDb();
  const users = db
    .prepare(
      `SELECT u.id, u.email, u.name, u.card_verified, u.email_verified, u.banned, u.created_at,
              COALESCE(s.plan, 'free') AS plan, COALESCE(s.status, 'active') AS plan_status,
              (SELECT COALESCE(SUM(cost_micros), 0) FROM usage_events e
                WHERE e.user_id = u.id AND e.month = ?) AS used_micros,
              (SELECT COUNT(DISTINCT family_id) FROM oauth_tokens t
                WHERE t.user_id = u.id AND t.kind = 'refresh' AND t.revoked = 0) AS devices
       FROM users u LEFT JOIN subscriptions s ON s.user_id = u.id
       ORDER BY u.created_at DESC LIMIT 500`,
    )
    .all(currentMonth());

  const totals = db
    .prepare(
      `SELECT COUNT(*) AS users,
              (SELECT COALESCE(SUM(cost_micros), 0) FROM usage_events WHERE month = ?) AS month_micros
       FROM users`,
    )
    .get(currentMonth());

  return NextResponse.json({ users, totals, month: currentMonth() });
}

/** Admin actions that never bypass target-user email verification. */
export async function POST(req: NextRequest) {
  const me = await getSessionUser();
  if (!isAdmin(me)) return NextResponse.json({ error: "forbidden" }, { status: 403 });

  const body = (await req.json().catch(() => null)) as
    | { action?: string; user_id?: string; plan?: string }
    | null;
  const userId = body?.user_id ?? "";
  const action = body?.action ?? "";
  if (!userId || !["ban", "unban", "revoke_devices", "verify_card", "set_plan"].includes(action)) {
    return NextResponse.json({ error: "bad_request" }, { status: 400 });
  }
  if (userId === me.id && action === "ban") {
    return NextResponse.json({ error: "cannot_ban_self" }, { status: 400 });
  }

  const db = getDb();
  const target = db
    .prepare("SELECT id, email_verified FROM users WHERE id = ?")
    .get(userId) as { id: string; email_verified: number } | undefined;
  if (!target) return NextResponse.json({ error: "not_found" }, { status: 404 });

  if (["verify_card", "set_plan"].includes(action) && !target.email_verified) {
    return NextResponse.json({ error: "email_verification_required" }, { status: 403 });
  }

  if (action === "ban") {
    db.prepare("UPDATE users SET banned = 1 WHERE id = ?").run(userId);
    db.prepare("UPDATE oauth_tokens SET revoked = 1 WHERE user_id = ?").run(userId);
  } else if (action === "unban") {
    db.prepare("UPDATE users SET banned = 0 WHERE id = ?").run(userId);
  } else if (action === "revoke_devices") {
    db.prepare("UPDATE oauth_tokens SET revoked = 1 WHERE user_id = ?").run(userId);
  } else if (action === "verify_card") {
    db.prepare("UPDATE users SET card_verified = 1 WHERE id = ?").run(userId);
  } else if (action === "set_plan") {
    const plan = body?.plan ?? "";
    if (!PLANS[plan as keyof typeof PLANS]) {
      return NextResponse.json({ error: "unknown_plan" }, { status: 400 });
    }
    db.prepare(
      `INSERT INTO subscriptions (user_id, plan, status, stripe_subscription_id, renews_at, updated_at)
       VALUES (?, ?, 'active', NULL, NULL, ?)
       ON CONFLICT(user_id) DO UPDATE SET
         plan = excluded.plan,
         status = 'active',
         renews_at = NULL,
         updated_at = excluded.updated_at`,
    ).run(userId, plan, now());
  }
  return NextResponse.json({ ok: true });
}
