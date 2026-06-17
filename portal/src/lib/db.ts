import Database from "better-sqlite3";
import fs from "node:fs";
import path from "node:path";

// Single SQLite connection, cached on globalThis so Next.js dev-mode HMR
// doesn't open a new handle per reload.
declare global {
  var __olpDb: Database.Database | undefined;
}

const SCHEMA = `
CREATE TABLE IF NOT EXISTS users (
  id                  TEXT PRIMARY KEY,
  email               TEXT NOT NULL UNIQUE COLLATE NOCASE,
  password_hash       TEXT NOT NULL,
  name                TEXT NOT NULL DEFAULT '',
  stripe_customer_id  TEXT,
  card_verified       INTEGER NOT NULL DEFAULT 0,
  created_at          INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS subscriptions (
  user_id                 TEXT PRIMARY KEY REFERENCES users(id),
  plan                    TEXT NOT NULL DEFAULT 'free',
  status                  TEXT NOT NULL DEFAULT 'active',
  stripe_subscription_id  TEXT,
  renews_at               INTEGER,
  updated_at              INTEGER NOT NULL
);

-- OAuth 2.0 device-authorization grants (RFC 8628), consumed by the
-- Clioloop CLI/TUI/desktop quick setup.
CREATE TABLE IF NOT EXISTS device_codes (
  device_code  TEXT PRIMARY KEY,
  user_code    TEXT NOT NULL UNIQUE,
  client_id    TEXT NOT NULL,
  scope        TEXT NOT NULL DEFAULT '',
  status       TEXT NOT NULL DEFAULT 'pending', -- pending|approved|denied|consumed
  user_id      TEXT,
  created_at   INTEGER NOT NULL,
  expires_at   INTEGER NOT NULL,
  poll_interval INTEGER NOT NULL DEFAULT 1
);

-- Access + refresh tokens issued to devices. Tokens are stored hashed
-- (sha256); 'family_id' groups a rotation chain so refresh-token reuse
-- revokes the whole session chain (OAuth 2.1 reuse detection).
CREATE TABLE IF NOT EXISTS oauth_tokens (
  id          TEXT PRIMARY KEY,
  user_id     TEXT NOT NULL REFERENCES users(id),
  kind        TEXT NOT NULL,              -- access|refresh
  token_hash  TEXT NOT NULL UNIQUE,
  family_id   TEXT NOT NULL,
  client_id   TEXT NOT NULL DEFAULT 'clio-cli',
  scope       TEXT NOT NULL DEFAULT '',
  revoked     INTEGER NOT NULL DEFAULT 0,
  rotated     INTEGER NOT NULL DEFAULT 0, -- refresh tokens: superseded by rotation
  created_at  INTEGER NOT NULL,
  expires_at  INTEGER
);
CREATE INDEX IF NOT EXISTS idx_oauth_tokens_family ON oauth_tokens(family_id);
CREATE INDEX IF NOT EXISTS idx_oauth_tokens_user ON oauth_tokens(user_id);

-- Per-request usage ledger; aggregated per calendar month for plan caps.
CREATE TABLE IF NOT EXISTS usage_events (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id           TEXT NOT NULL,
  month             TEXT NOT NULL,        -- 'YYYY-MM' (UTC)
  model             TEXT NOT NULL DEFAULT '',
  prompt_tokens     INTEGER NOT NULL DEFAULT 0,
  completion_tokens INTEGER NOT NULL DEFAULT 0,
  cost_micros       INTEGER NOT NULL DEFAULT 0,
  created_at        INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_usage_user_month ON usage_events(user_id, month);

-- Per-user daily counter for the one free model (FREE_OPENROUTER_MODEL). The
-- free daily allotment is an abuse guard: free users are blocked past it; paid
-- tiers keep using the model. Keyed by UTC day; old rows pruned.
CREATE TABLE IF NOT EXISTS free_model_requests (
  user_id  TEXT NOT NULL,
  day      TEXT NOT NULL,        -- 'YYYY-MM-DD' (UTC)
  count    INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, day)
);

-- Single-use email action tokens (verification / password reset),
-- stored hashed like every other credential.
CREATE TABLE IF NOT EXISTS action_tokens (
  id          TEXT PRIMARY KEY,
  user_id     TEXT NOT NULL REFERENCES users(id),
  kind        TEXT NOT NULL,               -- verify|reset
  token_hash  TEXT NOT NULL UNIQUE,
  used        INTEGER NOT NULL DEFAULT 0,
  created_at  INTEGER NOT NULL,
  expires_at  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_action_tokens_user ON action_tokens(user_id, kind);

-- Short-lived Telegram managed-bot onboarding sessions. The poll token is
-- stored hashed (bearer credential); the customer's created child-bot token is
-- stored AES-256-GCM encrypted and only long enough for one retrieval.
CREATE TABLE IF NOT EXISTS telegram_pairings (
  pairing_id          TEXT PRIMARY KEY,
  poll_token_hash     TEXT NOT NULL,
  suggested_username  TEXT NOT NULL,
  bot_name            TEXT NOT NULL DEFAULT 'Clioloop',
  status              TEXT NOT NULL DEFAULT 'pending', -- pending|ready|consumed
  owner_user_id       INTEGER,
  bot_username        TEXT,
  child_token_enc     TEXT,
  created_at          INTEGER NOT NULL,
  expires_at          INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tg_pairings_username ON telegram_pairings(suggested_username);
CREATE INDEX IF NOT EXISTS idx_tg_pairings_status ON telegram_pairings(status);
`;

/** Additive column migrations for databases created before a column existed. */
function migrate(db: Database.Database): void {
  const userCols = new Set(
    (db.prepare("PRAGMA table_info(users)").all() as { name: string }[]).map((c) => c.name),
  );
  if (!userCols.has("email_verified")) {
    db.exec("ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 0");
    // Grandfather accounts that predate verification so they aren't locked
    // out of flows that now require a verified address.
    db.exec("UPDATE users SET email_verified = 1");
  }
  if (!userCols.has("banned")) {
    db.exec("ALTER TABLE users ADD COLUMN banned INTEGER NOT NULL DEFAULT 0");
  }
}

export function getDb(): Database.Database {
  if (globalThis.__olpDb) return globalThis.__olpDb;
  const dir =
    process.env.PORTAL_DATA_DIR?.trim() || path.join(process.cwd(), "data");
  fs.mkdirSync(dir, { recursive: true });
  const db = new Database(path.join(dir, "portal.db"));
  db.pragma("journal_mode = WAL");
  db.pragma("foreign_keys = ON");
  db.exec(SCHEMA);
  migrate(db);
  globalThis.__olpDb = db;
  return db;
}

export function now(): number {
  return Math.floor(Date.now() / 1000);
}

export function currentMonth(): string {
  return new Date().toISOString().slice(0, 7);
}

/** UTC calendar day, 'YYYY-MM-DD'. */
export function utcDay(): string {
  return new Date().toISOString().slice(0, 10);
}

/** How many free-model requests this user has made today (UTC). */
export function freeModelDayCount(userId: string, day = utcDay()): number {
  const row = getDb()
    .prepare("SELECT count FROM free_model_requests WHERE user_id = ? AND day = ?")
    .get(userId, day) as { count: number } | undefined;
  return row?.count ?? 0;
}

/** Increment today's free-model counter for a user; prunes old rows opportunistically. */
export function incrFreeModelDay(userId: string, day = utcDay()): void {
  const db = getDb();
  db.prepare(
    `INSERT INTO free_model_requests (user_id, day, count) VALUES (?, ?, 1)
     ON CONFLICT(user_id, day) DO UPDATE SET count = count + 1`,
  ).run(userId, day);
  // Best-effort cleanup of stale days so the table stays tiny.
  db.prepare("DELETE FROM free_model_requests WHERE day < ?").run(day);
}

export interface UserRow {
  id: string;
  email: string;
  password_hash: string;
  name: string;
  stripe_customer_id: string | null;
  card_verified: number;
  email_verified: number;
  banned: number;
  created_at: number;
}

export interface SubscriptionRow {
  user_id: string;
  plan: string;
  status: string;
  stripe_subscription_id: string | null;
  renews_at: number | null;
  updated_at: number;
}

export function getUserById(id: string): UserRow | undefined {
  return getDb().prepare("SELECT * FROM users WHERE id = ?").get(id) as
    | UserRow
    | undefined;
}

export function getUserByEmail(email: string): UserRow | undefined {
  return getDb()
    .prepare("SELECT * FROM users WHERE email = ?")
    .get(email.trim()) as UserRow | undefined;
}

export function getSubscription(userId: string): SubscriptionRow | undefined {
  return getDb()
    .prepare("SELECT * FROM subscriptions WHERE user_id = ?")
    .get(userId) as SubscriptionRow | undefined;
}

export function setSubscription(
  userId: string,
  plan: string,
  fields: Partial<Pick<SubscriptionRow, "status" | "stripe_subscription_id" | "renews_at">> = {},
): void {
  const db = getDb();
  db.prepare(
    `INSERT INTO subscriptions (user_id, plan, status, stripe_subscription_id, renews_at, updated_at)
     VALUES (@userId, @plan, @status, @subId, @renewsAt, @now)
     ON CONFLICT(user_id) DO UPDATE SET
       plan = @plan, status = @status,
       stripe_subscription_id = COALESCE(@subId, stripe_subscription_id),
       renews_at = COALESCE(@renewsAt, renews_at),
       updated_at = @now`,
  ).run({
    userId,
    plan,
    status: fields.status ?? "active",
    subId: fields.stripe_subscription_id ?? null,
    renewsAt: fields.renews_at ?? null,
    now: now(),
  });
}

export function monthUsageMicros(userId: string, month = currentMonth()): number {
  const row = getDb()
    .prepare(
      "SELECT COALESCE(SUM(cost_micros), 0) AS total FROM usage_events WHERE user_id = ? AND month = ?",
    )
    .get(userId, month) as { total: number };
  return row.total;
}

export function recordUsage(
  userId: string,
  model: string,
  promptTokens: number,
  completionTokens: number,
  costMicros: number,
): void {
  getDb()
    .prepare(
      `INSERT INTO usage_events (user_id, month, model, prompt_tokens, completion_tokens, cost_micros, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?)`,
    )
    .run(userId, currentMonth(), model, promptTokens, completionTokens, costMicros, now());
}

// ---------------------------------------------------------------------------
// Telegram managed-bot onboarding pairings.
// ---------------------------------------------------------------------------

export interface TelegramPairingRow {
  pairing_id: string;
  poll_token_hash: string;
  suggested_username: string;
  bot_name: string;
  status: string; // pending|ready|consumed
  owner_user_id: number | null;
  bot_username: string | null;
  child_token_enc: string | null;
  created_at: number;
  expires_at: number;
}

export function createTelegramPairing(row: {
  pairingId: string;
  pollTokenHash: string;
  suggestedUsername: string;
  botName: string;
  ttlSeconds: number;
}): void {
  const ts = now();
  getDb()
    .prepare(
      `INSERT INTO telegram_pairings
         (pairing_id, poll_token_hash, suggested_username, bot_name, status, created_at, expires_at)
       VALUES (?, ?, ?, ?, 'pending', ?, ?)`,
    )
    .run(row.pairingId, row.pollTokenHash, row.suggestedUsername, row.botName, ts, ts + row.ttlSeconds);
}

export function getTelegramPairing(pairingId: string): TelegramPairingRow | undefined {
  return getDb()
    .prepare("SELECT * FROM telegram_pairings WHERE pairing_id = ?")
    .get(pairingId) as TelegramPairingRow | undefined;
}

/** Find the newest still-valid pending pairing for a suggested username — the
 *  correlation the manager-bot webhook uses to match a created child bot. */
export function findPendingTelegramPairingByUsername(username: string): TelegramPairingRow | undefined {
  return getDb()
    .prepare(
      `SELECT * FROM telegram_pairings
        WHERE suggested_username = ? AND status = 'pending' AND expires_at > ?
        ORDER BY created_at DESC LIMIT 1`,
    )
    .get(username, now()) as TelegramPairingRow | undefined;
}

export function markTelegramPairingReady(
  pairingId: string,
  encToken: string,
  botUsername: string,
  ownerUserId: number | null,
): void {
  getDb()
    .prepare(
      `UPDATE telegram_pairings
          SET status = 'ready', child_token_enc = ?, bot_username = ?, owner_user_id = ?
        WHERE pairing_id = ? AND status = 'pending'`,
    )
    .run(encToken, botUsername, ownerUserId, pairingId);
}

/** Mark a ready pairing consumed and wipe the stored token (single retrieval). */
export function consumeTelegramPairing(pairingId: string): void {
  getDb()
    .prepare(
      "UPDATE telegram_pairings SET status = 'consumed', child_token_enc = NULL WHERE pairing_id = ?",
    )
    .run(pairingId);
}

/** Best-effort cleanup of expired/old pairings so tokens never linger. */
export function pruneTelegramPairings(): void {
  getDb()
    .prepare(
      // Drop expired pending sessions and any consumed/ready row older than 1h.
      "DELETE FROM telegram_pairings WHERE (status = 'pending' AND expires_at < ?) OR created_at < ?",
    )
    .run(now(), now() - 3600);
}
