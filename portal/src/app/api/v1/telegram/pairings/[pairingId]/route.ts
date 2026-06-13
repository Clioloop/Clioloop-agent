import { NextRequest, NextResponse } from "next/server";
import { consumeTelegramPairing, getTelegramPairing, now } from "@/lib/db";
import { rateLimitResponse } from "@/lib/ratelimit";
import { hashToken } from "@/lib/tokens";
import { decryptSecret } from "@/lib/telegram";

export const runtime = "nodejs";

type Ctx = { params: Promise<{ pairingId: string }> };

/**
 * Poll a pairing. Auth: Authorization: Bearer <poll_token>.
 *
 * Returns { status: "waiting" | "expired" | "claimed" } while waiting/after
 * retrieval, and { status: "ready", token, bot_username, owner_user_id } exactly
 * once when the customer's bot has been created — the token is wiped immediately
 * after this single retrieval. (Status names match the Clio client proxy
 * contract: pending->waiting, consumed->claimed.)
 */
export async function GET(req: NextRequest, ctx: Ctx) {
  const limited = rateLimitResponse("telegram_poll", req);
  if (limited) return limited;

  const { pairingId } = await ctx.params;
  const bearer = (req.headers.get("authorization") ?? "").replace(/^Bearer\s+/i, "").trim();
  if (!bearer) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const row = getTelegramPairing(pairingId);
  // Same 401 for missing token and unknown/mismatched pairing — don't leak
  // which pairing ids exist to an unauthenticated caller.
  if (!row || hashToken(bearer) !== row.poll_token_hash) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  if (row.status === "consumed") {
    return NextResponse.json({ status: "claimed" });
  }

  if (row.status === "ready" && row.child_token_enc) {
    let token: string;
    try {
      token = decryptSecret(row.child_token_enc);
    } catch {
      return NextResponse.json({ status: "error" }, { status: 500 });
    }
    consumeTelegramPairing(pairingId); // single retrieval — wipe the token
    return NextResponse.json({
      status: "ready",
      token,
      bot_username: row.bot_username,
      owner_user_id: row.owner_user_id,
    });
  }

  if (row.expires_at < now()) {
    return NextResponse.json({ status: "expired" });
  }

  return NextResponse.json({ status: "waiting" });
}
