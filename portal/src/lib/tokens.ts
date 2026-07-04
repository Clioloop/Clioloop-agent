import crypto from "node:crypto";
import { getDb, now, stmt, UserRow } from "./db";
import { sessionSecret } from "./secret";

// Token prefixes make leaked credentials identifiable in logs/scanners.
export const ACCESS_PREFIX = "olp_at_";
export const REFRESH_PREFIX = "olp_rt_";

export const ACCESS_TOKEN_TTL_SECONDS = 3600; // CLI auto-refreshes 2 min early

export function randomToken(prefix: string): string {
  return prefix + crypto.randomBytes(32).toString("base64url");
}

/**
 * Access tokens are HS256 JWTs: the Clioloop CLI decodes the claims to check
 * the `inference:invoke` scope and `exp` before each request (it does not
 * verify the signature — the portal authenticates tokens by their stored
 * hash, so revocation still works instantly).
 */
function signAccessJwt(userId: string, scope: string, ttlSeconds: number): string {
  const b64 = (obj: unknown) => Buffer.from(JSON.stringify(obj)).toString("base64url");
  const nowSec = Math.floor(Date.now() / 1000);
  const header = b64({ alg: "HS256", typ: "JWT" });
  const payload = b64({
    sub: userId,
    scope,
    iat: nowSec,
    exp: nowSec + ttlSeconds,
    jti: crypto.randomUUID(),
    iss: "omni-loop-portal",
  });
  const sig = crypto
    .createHmac("sha256", sessionSecret())
    .update(`${header}.${payload}`)
    .digest("base64url");
  return `${header}.${payload}.${sig}`;
}

export function hashToken(token: string): string {
  return crypto.createHash("sha256").update(token).digest("hex");
}

/** Human-friendly device user code: XXXX-XXXX, unambiguous alphabet. */
export function generateUserCode(): string {
  const alphabet = "BCDFGHJKLMNPQRSTVWXYZ23456789";
  const pick = () =>
    alphabet[crypto.randomInt(alphabet.length)];
  const part = () => Array.from({ length: 4 }, pick).join("");
  return `${part()}-${part()}`;
}

export interface IssuedTokenPair {
  access_token: string;
  refresh_token: string;
  token_type: "Bearer";
  scope: string;
  expires_in: number;
}

/** Issue a fresh access+refresh pair in a (possibly new) rotation family. */
export function issueTokenPair(
  userId: string,
  clientId: string,
  scope: string,
  familyId?: string,
): IssuedTokenPair {
  const db = getDb();
  const family = familyId ?? crypto.randomUUID();
  const access = signAccessJwt(userId, scope || "inference:invoke", ACCESS_TOKEN_TTL_SECONDS);
  const refresh = randomToken(REFRESH_PREFIX);
  const ts = now();
  const insert = db.prepare(
    `INSERT INTO oauth_tokens (id, user_id, kind, token_hash, family_id, client_id, scope, created_at, expires_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
  );
  insert.run(crypto.randomUUID(), userId, "access", hashToken(access), family, clientId, scope, ts, ts + ACCESS_TOKEN_TTL_SECONDS);
  insert.run(crypto.randomUUID(), userId, "refresh", hashToken(refresh), family, clientId, scope, ts, null);
  return {
    access_token: access,
    refresh_token: refresh,
    token_type: "Bearer",
    scope,
    expires_in: ACCESS_TOKEN_TTL_SECONDS,
  };
}

export interface RefreshResult {
  ok: boolean;
  error?: "invalid_grant" | "refresh_token_reused";
  pair?: IssuedTokenPair;
}

/** Rotate a refresh token (single-use). Reuse revokes the whole family. */
export function rotateRefreshToken(refreshToken: string): RefreshResult {
  const db = getDb();
  const row = db
    .prepare("SELECT * FROM oauth_tokens WHERE token_hash = ? AND kind = 'refresh'")
    .get(hashToken(refreshToken)) as
    | { id: string; user_id: string; family_id: string; client_id: string; scope: string; revoked: number; rotated: number }
    | undefined;
  if (!row) return { ok: false, error: "invalid_grant" };
  if (row.rotated) {
    // OAuth 2.1 reuse detection: a rotated token came back — treat the whole
    // chain as compromised. The Clioloop CLI surfaces this error code with a
    // dedicated, actionable message.
    db.prepare("UPDATE oauth_tokens SET revoked = 1 WHERE family_id = ?").run(row.family_id);
    return { ok: false, error: "refresh_token_reused" };
  }
  if (row.revoked) return { ok: false, error: "invalid_grant" };
  db.prepare("UPDATE oauth_tokens SET rotated = 1, revoked = 1 WHERE id = ?").run(row.id);
  const pair = issueTokenPair(row.user_id, row.client_id, row.scope, row.family_id);
  return { ok: true, pair };
}

export interface BearerIdentity {
  user: UserRow;
  via: "oauth";
}

/**
 * Resolve a Bearer credential. The portal is strictly the Clioloop agent's
 * gateway — the only accepted credential is the device-flow OAuth access
 * token (a JWT, or a legacy opaque olp_at_ token), authenticated by its
 * stored hash. There are no standalone API keys.
 */
export function resolveBearer(authorization: string | null): BearerIdentity | null {
  const token = (authorization ?? "").replace(/^Bearer\s+/i, "").trim();
  if (!token) return null;
  if (!token.startsWith("eyJ") && !token.startsWith(ACCESS_PREFIX)) return null;
  const hash = hashToken(token);

  const user = stmt(
    `SELECT users.* FROM oauth_tokens
      JOIN users ON users.id = oauth_tokens.user_id
     WHERE oauth_tokens.token_hash = ? AND oauth_tokens.kind = 'access'
       AND oauth_tokens.revoked = 0 AND oauth_tokens.expires_at > ?`,
  ).get(hash, now()) as UserRow | undefined;
  // Suspended accounts lose API access immediately, tokens or not.
  if (!user || user.banned) return null;
  return { user, via: "oauth" };
}
