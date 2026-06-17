import { beforeAll, describe, expect, it } from "vitest";

beforeAll(() => {
  process.env.TELEGRAM_ONBOARDING_ENC_KEY = "test-encryption-passphrase-for-vitest";
  process.env.TELEGRAM_MANAGER_BOT_USERNAME = "ClioSetupBot";
  process.env.TELEGRAM_WEBHOOK_SECRET = "test-webhook-secret";
});

describe("telegram lib", () => {
  it("encrypts and decrypts a token round-trip", async () => {
    const { encryptSecret, decryptSecret } = await import("./telegram");
    const token = "123456789:AAH1234567890abcdefghijklmnopqrstuv";
    const enc = encryptSecret(token);
    expect(enc).not.toContain(token);
    expect(enc.split(":")).toHaveLength(3); // iv:tag:ciphertext
    expect(decryptSecret(enc)).toBe(token);
  });

  it("uses a fresh IV each time (ciphertext differs)", async () => {
    const { encryptSecret } = await import("./telegram");
    const a = encryptSecret("same-plaintext");
    const b = encryptSecret("same-plaintext");
    expect(a).not.toBe(b);
  });

  it("validates Telegram bot token shape", async () => {
    const { isValidTelegramBotToken } = await import("./telegram");
    expect(isValidTelegramBotToken("123456789:AAH1234567890abcdefghijklmnopqrstuv")).toBe(true);
    expect(isValidTelegramBotToken("not-a-token")).toBe(false);
    expect(isValidTelegramBotToken("")).toBe(false);
    expect(isValidTelegramBotToken(null)).toBe(false);
  });

  it("generates a unique clio_<slug>_bot username", async () => {
    const { generateBotUsername } = await import("./telegram");
    const u = generateBotUsername();
    expect(u).toMatch(/^clio_[a-z2-7]{16}_bot$/);
    expect(generateBotUsername()).not.toBe(u);
  });

  it("builds a t.me managed-bot deep link with the manager username", async () => {
    const { buildDeepLink } = await import("./telegram");
    const link = buildDeepLink("clio_abc_bot", "My Bot");
    expect(link).toContain("https://t.me/newbot/ClioSetupBot/clio_abc_bot");
    expect(link).toContain("name=My%20Bot");
  });

  describe("parseCreatedBot", () => {
    const TOKEN = "987654321:AAGabcdefghijklmnopqrstuvwxyz1234567";

    it("extracts a managed_bot payload", async () => {
      const { parseCreatedBot } = await import("./telegram");
      const got = parseCreatedBot({
        managed_bot: {
          bot: { id: 999, token: TOKEN, username: "@clio_xyz_bot" },
          user: { id: 4242 },
        },
      });
      expect(got).toEqual({ botId: 999, username: "clio_xyz_bot", ownerUserId: 4242, inlineToken: TOKEN });
    });

    it("extracts the new_bot alias without an inline token", async () => {
      const { parseCreatedBot } = await import("./telegram");
      const got = parseCreatedBot({
        new_bot: {
          bot: { id: 777, username: "clio_flat_bot" },
          user: { id: 77 },
        },
      });
      expect(got).toEqual({ botId: 777, username: "clio_flat_bot", ownerUserId: 77 });
    });

    it("returns null for an unrelated update", async () => {
      const { parseCreatedBot } = await import("./telegram");
      expect(parseCreatedBot({ message: { text: "hi" } })).toBeNull();
      expect(parseCreatedBot(null)).toBeNull();
    });

    it("returns null when the token is malformed", async () => {
      const { parseCreatedBot } = await import("./telegram");
      expect(parseCreatedBot({ new_bot: { token: "bad", username: "x" } })).toBeNull();
    });
  });
});
