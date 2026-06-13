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
  token: string;
  username: string;
  ownerUserId: number | null;
}

/**
 * Extract a created managed bot from a Telegram manager-bot webhook update.
 *
 * Telegram's managed-bot creation surfaces the child token to the manager bot;
 * the exact update envelope is verified against the live API during webhook
 * setup, so this parser is deliberately tolerant: it looks for the token,
 * the child bot username, and the creating user id wherever Telegram places
 * them. Returns null when the update isn't a bot-created event.
 */
export function parseCreatedBot(update: unknown): CreatedBot | null {
  const u = update as Record<string, unknown> | null;
  if (!u || typeof u !== "object") return null;

  // Common shapes: a dedicated `managed_bot`/`new_bot` object, or fields on
  // a business_connection/message. Search a few likely containers.
  const containers: Record<string, unknown>[] = [];
  for (const key of ["managed_bot", "new_bot", "bot", "business_connection"]) {
    const v = u[key];
    if (v && typeof v === "object") containers.push(v as Record<string, unknown>);
  }
  containers.push(u); // also allow flat fields at the top level

  let token: string | null = null;
  let username: string | null = null;
  let ownerUserId: number | null = null;

  for (const c of containers) {
    for (const tk of ["token", "bot_token", "child_token"]) {
      if (isValidTelegramBotToken(c[tk])) token = c[tk] as string;
    }
    for (const un of ["username", "bot_username"]) {
      const val = c[un];
      if (typeof val === "string" && val) username = val.replace(/^@/, "");
    }
    for (const oid of ["owner_user_id", "user_id", "creator_id"]) {
      const val = c[oid];
      if (typeof val === "number" && Number.isInteger(val) && val > 0) ownerUserId = val;
      else if (typeof val === "string" && /^\d+$/.test(val)) ownerUserId = parseInt(val, 10);
    }
    // Telegram nests the creating user under `from`/`user`.
    for (const userKey of ["from", "user"]) {
      const who = c[userKey] as Record<string, unknown> | undefined;
      if (who && typeof who.id === "number" && who.id > 0) ownerUserId = who.id;
    }
  }

  if (!token || !username) return null;
  return { token, username, ownerUserId };
}
