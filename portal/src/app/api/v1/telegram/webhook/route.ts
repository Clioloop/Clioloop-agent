import { NextRequest, NextResponse } from "next/server";
import { findPendingTelegramPairingByUsername, markTelegramPairingReady } from "@/lib/db";
import { encryptSecret, parseCreatedBot, webhookSecret } from "@/lib/telegram";

export const runtime = "nodejs";

/**
 * Telegram webhook for the manager/factory bot.
 *
 * When a customer confirms creation of their managed child bot, Telegram posts
 * the new bot's details here. We correlate it to a pending pairing by the
 * suggested username, store the child token encrypted, and flip the pairing to
 * "ready" so the customer's install can retrieve it on its next poll.
 *
 * Auth: the secret Telegram echoes in X-Telegram-Bot-Api-Secret-Token (set when
 * registering the webhook). We always answer 200 on authenticated calls so
 * Telegram doesn't retry-storm, even when there's nothing to correlate.
 */
export async function POST(req: NextRequest) {
  const expected = webhookSecret();
  const got = req.headers.get("x-telegram-bot-api-secret-token");
  if (!expected || got !== expected) {
    return NextResponse.json({ ok: false }, { status: 401 });
  }

  const update = await req.json().catch(() => null);
  const created = parseCreatedBot(update);
  if (!created) {
    return NextResponse.json({ ok: true });
  }

  const pairing = findPendingTelegramPairingByUsername(created.username);
  if (!pairing) {
    // No matching pending pairing (already consumed, expired, or a username we
    // didn't issue) — acknowledge without storing anything.
    return NextResponse.json({ ok: true });
  }

  markTelegramPairingReady(
    pairing.pairing_id,
    encryptSecret(created.token),
    created.username,
    created.ownerUserId,
  );
  return NextResponse.json({ ok: true });
}
