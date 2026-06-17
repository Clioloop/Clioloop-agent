import { NextRequest, NextResponse } from "next/server";
import { findPendingTelegramPairingByUsername, markTelegramPairingReady } from "@/lib/db";
import {
  encryptSecret,
  getManagedBotToken,
  isValidTelegramBotToken,
  parseCreatedBot,
  webhookSecret,
} from "@/lib/telegram";

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

  // Bot API 9.6: the managed_bot update carries the child bot's id, not its
  // token — fetch it via getManagedBotToken (unless a future API inlines it).
  const token = created.inlineToken ?? (await getManagedBotToken(created.botId));
  if (!isValidTelegramBotToken(token)) {
    // Couldn't obtain the token (manager not configured / API hiccup). Leave the
    // pairing pending so the customer's install keeps polling; ack to Telegram.
    console.error(
      `[telegram] getManagedBotToken returned no valid token for bot ${created.botId} ` +
        `(pairing ${pairing.pairing_id}). Check TELEGRAM_MANAGER_BOT_TOKEN and that ` +
        `the manager bot has bot-management mode enabled.`,
    );
    return NextResponse.json({ ok: true });
  }

  try {
    markTelegramPairingReady(
      pairing.pairing_id,
      encryptSecret(token),
      created.username,
      created.ownerUserId,
    );
  } catch (err) {
    // encryptSecret throws when TELEGRAM_ONBOARDING_ENC_KEY is missing/invalid
    // (or the DB write fails). Without this guard the handler 500s, the pairing
    // silently stays "pending", and the customer's loading screen hangs forever.
    // Log loudly so the misconfiguration is visible, and still ack so Telegram
    // doesn't retry-storm.
    console.error(
      `[telegram] failed to store child token for pairing ${pairing.pairing_id} ` +
        `(check TELEGRAM_ONBOARDING_ENC_KEY):`,
      err,
    );
    return NextResponse.json({ ok: true });
  }

  return NextResponse.json({ ok: true });
}
