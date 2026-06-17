import { NextRequest, NextResponse } from "next/server";
import crypto from "node:crypto";
import { createTelegramPairing, pruneTelegramPairings } from "@/lib/db";
import { rateLimitResponse } from "@/lib/ratelimit";
import { hashToken, randomToken } from "@/lib/tokens";
import {
  buildDeepLink,
  DEFAULT_BOT_NAME,
  generateBotUsername,
  PAIRING_TTL_SECONDS,
  POLL_TOKEN_PREFIX,
} from "@/lib/telegram";

export const runtime = "nodejs";

/**
 * Create a Telegram managed-bot onboarding pairing.
 *
 * Body: { bot_name?: string }
 * Returns: { pairing_id, poll_token, suggested_username, deep_link, qr_payload,
 *            expires_at } — the customer's Clio install shows the QR/deep link
 * and polls GET /v1/telegram/pairings/{pairing_id} with the poll_token.
 */
export async function POST(req: NextRequest) {
  const limited = rateLimitResponse("telegram_pairing", req);
  if (limited) return limited;

  const body = (await req.json().catch(() => ({}))) as { bot_name?: unknown };
  const botName =
    typeof body?.bot_name === "string" && body.bot_name.trim()
      ? body.bot_name.trim().slice(0, 64)
      : DEFAULT_BOT_NAME;

  pruneTelegramPairings();

  const pairingId = crypto.randomUUID();
  const pollToken = randomToken(POLL_TOKEN_PREFIX);
  const suggestedUsername = generateBotUsername();

  createTelegramPairing({
    pairingId,
    pollTokenHash: hashToken(pollToken),
    suggestedUsername,
    botName,
    ttlSeconds: PAIRING_TTL_SECONDS,
  });

  const deepLink = buildDeepLink(suggestedUsername, botName);
  const expiresAt = new Date((Math.floor(Date.now() / 1000) + PAIRING_TTL_SECONDS) * 1000).toISOString();

  return NextResponse.json(
    {
      pairing_id: pairingId,
      poll_token: pollToken,
      suggested_username: suggestedUsername,
      deep_link: deepLink,
      qr_payload: deepLink,
      expires_at: expiresAt,
    },
    { status: 201 },
  );
}
