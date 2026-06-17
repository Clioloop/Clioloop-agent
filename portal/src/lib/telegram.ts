import crypto from "node:crypto";

/**
 * Hosted Telegram managed-bot onboarding helpers.
 *
 * The customer's Clioloop install POSTs to create a pairing, shows a QR/deep
 * link, and polls until their own (customer-owned) bot has been created via
 * Telegram's managed-bot flow. The manager/factory bot's webhook reports the
 * new child-bot token here; we hold it encrypted just long enough for the
 * customer's install to retrieve it once, then drop it.
 *
 * Config (env, set in the portal service environment — see deploy notes):
 *   TELEGRAM_MANAGER_BOT_TOKEN     the shared manager/factory bot token
 *   TELEGRAM_MANAGER_BOT_USERNAME  the manager bot @username (no leading @)
 *   TELEGRAM_WEBHOOK_SECRET        secret-token set on the Telegram webhook
 *   TELEGRAM_ONBOARDING_ENC_KEY    32-byte key (hex/base64) or any passphrase
 */

export const POLL_TOKEN_PREFIX = "olp_tg_";
export const PAIRING_TTL_SECONDS = 30 * 60; // 30 minutes to scan + confirm
export const DEFAULT_BOT_NAME = "Clioloop";

const _USERNAME_SLUG_ALPHABET = "abcdefghijklmnopqrstuvwxyz234567";
const _TELEGRAM_BOT_TOKEN_RE = /^\d+:[A-Za-z0-9_-]{30,}$/;

export function isValidTelegramBotToken(token: unknown): token is string {
  return typeof token === "string" && _TELEGRAM_BOT_TOKEN_RE.test(token);
}

/** base32-ish slug; 16 chars of 32-symbol alphabet = 80 bits of entropy. */
export function generateUsernameSlug(length = 16): string {
  let out = "";
  for (let i = 0; i < length; i++) {
    out += _USERNAME_SLUG_ALPHABET[crypto.randomInt(_USERNAME_SLUG_ALPHABET.length)];
  }
  return out;
}

/** Suggested child-bot username, e.g. clio_<slug>_bot. The slug carries the
 *  entropy the webhook uses to correlate a created bot back to its pairing. */
export function generateBotUsername(): string {
  return `clio_${generateUsernameSlug()}_bot`;
}

export function managerBotUsername(): string {
  return (process.env.TELEGRAM_MANAGER_BOT_USERNAME || "ClioSetupBot").replace(/^@/, "");
}

export function managerBotToken(): string | undefined {
  return process.env.TELEGRAM_MANAGER_BOT_TOKEN?.trim() || undefined;
}

export function webhookSecret(): string | undefined {
  return process.env.TELEGRAM_WEBHOOK_SECRET?.trim() || undefined;
}

/** Build the t.me managed-bot creation deep link (matches the CLI client). */
export function buildDeepLink(suggestedUsername: string, botName = DEFAULT_BOT_NAME): string {
  const base =
    `https://t.me/newbot/${encodeURIComponent(managerBotUsername())}/` +
    `${encodeURIComponent(suggestedUsername)}`;
  return botName ? `${base}?name=${encodeURIComponent(botName)}` : base;
}

// ---------------------------------------------------------------------------
// Child-bot-token encryption at rest (AES-256-GCM).
// ---------------------------------------------------------------------------

function encKey(): Buffer {
  const raw = process.env.TELEGRAM_ONBOARDING_ENC_KEY?.trim();
  if (!raw) {
    throw new Error("TELEGRAM_ONBOARDING_ENC_KEY is not set");
  }
  if (/^[0-9a-fA-F]{64}$/.test(raw)) return Buffer.from(raw, "hex");
  const b = Buffer.from(raw, "base64");
  if (b.length === 32) return b;
  // Any other passphrase is stretched to 32 bytes; deterministic so a restart
  // can still decrypt tokens written before it.
  return crypto.createHash("sha256").update(raw).digest();
}

export function encryptSecret(plain: string): string {
  const iv = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv("aes-256-gcm", encKey(), iv);
  const ct = Buffer.concat([cipher.update(plain, "utf8"), cipher.final()]);
  const tag = cipher.getAuthTag();
  return [iv.toString("hex"), tag.toString("hex"), ct.toString("hex")].join(":");
}

export function decryptSecret(enc: string): string {
  const [ivHex, tagHex, ctHex] = enc.split(":");
  if (!ivHex || !tagHex || !ctHex) throw new Error("malformed ciphertext");
  const decipher = crypto.createDecipheriv("aes-256-gcm", encKey(), Buffer.from(ivHex, "hex"));
  decipher.setAuthTag(Buffer.from(tagHex, "hex"));
  return Buffer.concat([decipher.update(Buffer.from(ctHex, "hex")), decipher.final()]).toString("utf8");
}

// ---------------------------------------------------------------------------
// Webhook payload parsing — correlate a created managed bot to its pairing.
// ---------------------------------------------------------------------------

export interface CreatedBot {
  /** The new (child) bot's user id — pass to getManagedBotToken to get its token. */
  botId: number;
  username: string;
  ownerUserId: number | null;
  /** Token, only if Telegram ever inlines it (it normally does not). */
  inlineToken?: string;
}

/**
 * Parse a Telegram **managed-bot** webhook update (Bot API 9.6+).
 *
 * The real envelope is ``update.managed_bot`` → ``ManagedBotUpdated`` with:
 *   - ``bot``  (User): the new child bot — ``id`` + ``username``
 *   - ``user`` (User): the customer who created it — ``id`` = owner
 * The child token is NOT in the update; fetch it with ``getManagedBotToken``
 * using ``botId``. We stay tolerant about an inline token in case Telegram ever
 * adds one. Returns null when the update isn't a managed-bot-created event.
 */
export function parseCreatedBot(update: unknown): CreatedBot | null {
  const u = update as Record<string, unknown> | null;
  if (!u || typeof u !== "object") return null;

  const mb = (u.managed_bot ?? u.new_bot) as Record<string, unknown> | undefined;
  if (!mb || typeof mb !== "object") return null;

  const botUser = mb.bot as Record<string, unknown> | undefined;
  const creator = mb.user as Record<string, unknown> | undefined;

  const botId =
    botUser && typeof botUser.id === "number" && botUser.id > 0 ? botUser.id : null;
  const usernameRaw = botUser && typeof botUser.username === "string" ? botUser.username : "";
  const username = usernameRaw ? usernameRaw.replace(/^@/, "") : "";

  let ownerUserId: number | null = null;
  if (creator && typeof creator.id === "number" && creator.id > 0) ownerUserId = creator.id;

  if (!botId || !username) return null;

  // Defensive: accept an inline token if a future API revision provides one
  // (on the managed_bot envelope or the bot object).
  let inlineToken: string | undefined;
  for (const src of [mb, botUser]) {
    if (!src) continue;
    for (const tk of ["token", "bot_token", "child_token"]) {
      if (isValidTelegramBotToken(src[tk])) inlineToken = src[tk] as string;
    }
  }

  return { botId, username, ownerUserId, inlineToken };
}

/**
 * Fetch a managed (child) bot's access token via the manager bot.
 * Bot API 9.6 ``getManagedBotToken`` — called with the manager bot token and
 * the child bot's id. Returns the child token, or null on any failure.
 *
 * The API parameter is ``user_id`` (a bot's id IS its user id), NOT ``bot_id``:
 * Telegram silently ignores an unknown ``bot_id`` and then rejects the call with
 * "invalid user_id specified", so sending ``bot_id`` made every fetch fail and
 * left the onboarding pairing stuck pending. Verified live against the Bot API.
 */
export async function getManagedBotToken(botId: number): Promise<string | null> {
  const manager = managerBotToken();
  if (!manager) return null;
  try {
    const resp = await fetch(`https://api.telegram.org/bot${manager}/getManagedBotToken`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: botId }),
    });
    const data = (await resp.json().catch(() => null)) as
      | { ok?: boolean; result?: unknown }
      | null;
    if (!data?.ok) return null;
    // result may be the token string, or an object carrying it.
    const r = data.result as unknown;
    if (isValidTelegramBotToken(r)) return r as string;
    if (r && typeof r === "object") {
      for (const k of ["token", "bot_token", "access_token"]) {
        const v = (r as Record<string, unknown>)[k];
        if (isValidTelegramBotToken(v)) return v as string;
      }
    }
    return null;
  } catch {
    return null;
  }
}
