import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { NextRequest } from "next/server";
import { beforeAll, describe, expect, it } from "vitest";

// Isolated DB + config must be set before any getDb()/encKey() call.
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), "portal-tg-test-"));
process.env.PORTAL_DATA_DIR = TMP;
process.env.TELEGRAM_ONBOARDING_ENC_KEY = "vitest-enc-key-passphrase";
process.env.TELEGRAM_WEBHOOK_SECRET = "vitest-webhook-secret";
process.env.TELEGRAM_MANAGER_BOT_USERNAME = "ClioSetupBot";

const CHILD_TOKEN = "111222333:AAH_child_bot_token_abcdefghijklmnop";

let createPairing: typeof import("./pairings/route").POST;
let pollPairing: typeof import("./pairings/[pairingId]/route").GET;
let webhook: typeof import("./webhook/route").POST;
let db: typeof import("@/lib/db");

beforeAll(async () => {
  createPairing = (await import("./pairings/route")).POST;
  pollPairing = (await import("./pairings/[pairingId]/route")).GET;
  webhook = (await import("./webhook/route")).POST;
  db = await import("@/lib/db");
});

function postJson(url: string, body: unknown, headers: Record<string, string> = {}): NextRequest {
  return new NextRequest(url, {
    method: "POST",
    body: JSON.stringify(body),
    headers: { "content-type": "application/json", "x-forwarded-for": rndIp(), ...headers },
  });
}

function getReq(url: string, headers: Record<string, string> = {}): NextRequest {
  return new NextRequest(url, { headers: { "x-forwarded-for": rndIp(), ...headers } });
}

let ipCounter = 0;
function rndIp(): string {
  ipCounter += 1;
  return `10.0.0.${ipCounter % 250}`;
}

async function newPairing(botName = "Clioloop") {
  const res = await createPairing(postJson("http://localhost/api/v1/telegram/pairings", { bot_name: botName }));
  expect(res.status).toBe(201);
  return res.json();
}

describe("telegram onboarding routes", () => {
  it("creates a pairing with deep link, QR payload, and a poll token", async () => {
    const data = await newPairing("My Agent");
    expect(data.pairing_id).toBeTruthy();
    expect(data.poll_token).toMatch(/^olp_tg_/);
    expect(data.suggested_username).toMatch(/^clio_[a-z2-7]{16}_bot$/);
    expect(data.deep_link).toContain("https://t.me/newbot/ClioSetupBot/");
    expect(data.qr_payload).toBe(data.deep_link);
    expect(typeof data.expires_at).toBe("string");
  });

  it("polls pending, then ready exactly once after the webhook fires", async () => {
    const p = await newPairing();

    // Pending before the bot is created.
    const pending = await pollPairing(
      getReq(`http://localhost/api/v1/telegram/pairings/${p.pairing_id}`, { authorization: `Bearer ${p.poll_token}` }),
      { params: Promise.resolve({ pairingId: p.pairing_id }) },
    );
    expect(await pending.json()).toEqual({ status: "waiting" });

    // Manager-bot webhook delivers the created child bot.
    const hook = await webhook(
      postJson(
        "http://localhost/api/v1/telegram/webhook",
        { managed_bot: { bot: { id: 424242, username: p.suggested_username, token: CHILD_TOKEN }, user: { id: 555 } } },
        { "x-telegram-bot-api-secret-token": "vitest-webhook-secret" },
      ),
    );
    expect(hook.status).toBe(200);

    // Token is stored ENCRYPTED, not in the clear.
    const row = db.getTelegramPairing(p.pairing_id)!;
    expect(row.status).toBe("ready");
    expect(row.child_token_enc).toBeTruthy();
    expect(row.child_token_enc).not.toContain(CHILD_TOKEN);

    // First poll returns the token...
    const ready = await pollPairing(
      getReq(`http://localhost/api/v1/telegram/pairings/${p.pairing_id}`, { authorization: `Bearer ${p.poll_token}` }),
      { params: Promise.resolve({ pairingId: p.pairing_id }) },
    );
    expect(await ready.json()).toEqual({
      status: "ready",
      token: CHILD_TOKEN,
      bot_username: p.suggested_username,
      owner_user_id: 555,
    });

    // ...and the token is wiped after the single retrieval.
    const consumed = await pollPairing(
      getReq(`http://localhost/api/v1/telegram/pairings/${p.pairing_id}`, { authorization: `Bearer ${p.poll_token}` }),
      { params: Promise.resolve({ pairingId: p.pairing_id }) },
    );
    expect(await consumed.json()).toEqual({ status: "claimed" });
    expect(db.getTelegramPairing(p.pairing_id)!.child_token_enc).toBeNull();
  });

  it("rejects polling with a wrong or missing bearer token (401)", async () => {
    const p = await newPairing();

    const wrong = await pollPairing(
      getReq(`http://localhost/api/v1/telegram/pairings/${p.pairing_id}`, { authorization: "Bearer not-the-token" }),
      { params: Promise.resolve({ pairingId: p.pairing_id }) },
    );
    expect(wrong.status).toBe(401);

    const missing = await pollPairing(
      getReq(`http://localhost/api/v1/telegram/pairings/${p.pairing_id}`),
      { params: Promise.resolve({ pairingId: p.pairing_id }) },
    );
    expect(missing.status).toBe(401);
  });

  it("returns 'expired' for a pairing past its TTL", async () => {
    const pairingId = "expired-pairing-id";
    const pollToken = "olp_tg_expiredtoken";
    db.createTelegramPairing({
      pairingId,
      pollTokenHash: (await import("@/lib/tokens")).hashToken(pollToken),
      suggestedUsername: "clio_expired_bot",
      botName: "Clioloop",
      ttlSeconds: -10, // already expired
    });
    const res = await pollPairing(
      getReq(`http://localhost/api/v1/telegram/pairings/${pairingId}`, { authorization: `Bearer ${pollToken}` }),
      { params: Promise.resolve({ pairingId }) },
    );
    expect(await res.json()).toEqual({ status: "expired" });
  });

  it("rejects the webhook without the correct secret token (401)", async () => {
    const bad = await webhook(
      postJson(
        "http://localhost/api/v1/telegram/webhook",
        { managed_bot: { bot: { id: 1, username: "clio_x_bot", token: CHILD_TOKEN } } },
        { "x-telegram-bot-api-secret-token": "wrong-secret" },
      ),
    );
    expect(bad.status).toBe(401);
  });

  it("acknowledges (200) an authenticated webhook with no matching pairing", async () => {
    const res = await webhook(
      postJson(
        "http://localhost/api/v1/telegram/webhook",
        { managed_bot: { bot: { id: 2, username: "clio_never_issued_bot", token: CHILD_TOKEN } } },
        { "x-telegram-bot-api-secret-token": "vitest-webhook-secret" },
      ),
    );
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ ok: true });
  });
});
