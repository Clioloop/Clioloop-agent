import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import crypto from "node:crypto";
import { beforeAll, describe, expect, it } from "vitest";

// Isolated DB must be set before any getDb() call.
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), "portal-tokens-test-"));
process.env.PORTAL_DATA_DIR = TMP;

let db: typeof import("./db");
let tokens: typeof import("./tokens");

function createUser(id: string, banned = 0): void {
  db.stmt(
    `INSERT INTO users (id, email, password_hash, name, banned, created_at)
     VALUES (?, ?, 'x', '', ?, ?)`,
  ).run(id, `${id}@example.com`, banned, db.now());
}

beforeAll(async () => {
  db = await import("./db");
  tokens = await import("./tokens");
});

describe("resolveBearer", () => {
  it("resolves a freshly issued access token to its user", () => {
    createUser("user-ok");
    const pair = tokens.issueTokenPair("user-ok", "clio-cli", "inference:invoke");
    const identity = tokens.resolveBearer(`Bearer ${pair.access_token}`);
    expect(identity).not.toBeNull();
    expect(identity!.user.id).toBe("user-ok");
    expect(identity!.via).toBe("oauth");
  });

  it("rejects banned users even with a valid token", () => {
    createUser("user-banned", 1);
    const pair = tokens.issueTokenPair("user-banned", "clio-cli", "inference:invoke");
    expect(tokens.resolveBearer(`Bearer ${pair.access_token}`)).toBeNull();
  });

  it("rejects revoked tokens", () => {
    createUser("user-revoked");
    const pair = tokens.issueTokenPair("user-revoked", "clio-cli", "inference:invoke");
    db.stmt("UPDATE oauth_tokens SET revoked = 1 WHERE token_hash = ?").run(
      tokens.hashToken(pair.access_token),
    );
    expect(tokens.resolveBearer(`Bearer ${pair.access_token}`)).toBeNull();
  });

  it("rejects expired tokens", () => {
    createUser("user-expired");
    const pair = tokens.issueTokenPair("user-expired", "clio-cli", "inference:invoke");
    db.stmt("UPDATE oauth_tokens SET expires_at = ? WHERE token_hash = ?").run(
      db.now() - 10,
      tokens.hashToken(pair.access_token),
    );
    expect(tokens.resolveBearer(`Bearer ${pair.access_token}`)).toBeNull();
  });

  it("rejects garbage, missing, and unprefixed credentials", () => {
    expect(tokens.resolveBearer(null)).toBeNull();
    expect(tokens.resolveBearer("")).toBeNull();
    expect(tokens.resolveBearer("Bearer not-a-token")).toBeNull();
    expect(tokens.resolveBearer(`Bearer olp_at_${crypto.randomBytes(32).toString("base64url")}`)).toBeNull();
  });
});
