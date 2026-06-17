import { beforeEach, describe, expect, it, vi } from "vitest";
import type { NextRequest } from "next/server";

const db = vi.hoisted(() => ({
  freeModelDayCount: vi.fn(),
  getSubscription: vi.fn(),
  hasActiveMeteringAlert: vi.fn(),
  incrFreeModelDay: vi.fn(),
  monthUsageMicros: vi.fn(),
  recordMeteringAlert: vi.fn(),
  recordUsage: vi.fn(),
}));

const tokens = vi.hoisted(() => ({
  resolveBearer: vi.fn(),
}));

vi.mock("@/lib/db", () => db);
vi.mock("@/lib/tokens", () => tokens);
vi.mock("@/lib/ratelimit", () => ({ rateLimit: vi.fn(() => null) }));
vi.mock("@/lib/inference-upstream", () => ({
  selectInferenceUpstream: () => ({
    kind: "openrouter",
    base: "https://openrouter.test/api/v1",
    key: "openrouter-key",
  }),
}));

import { POST } from "./route";

function request(body: Record<string, unknown>) {
  return new Request("https://portal.test/api/v1/chat/completions", {
    method: "POST",
    headers: {
      authorization: "Bearer portal-token",
      "content-type": "application/json",
    },
    body: JSON.stringify(body),
  }) as NextRequest;
}

describe("chat completion metering safety", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    db.freeModelDayCount.mockReturnValue(0);
    db.getSubscription.mockReturnValue({ plan: "pro", status: "active" });
    db.hasActiveMeteringAlert.mockReturnValue(false);
    db.monthUsageMicros.mockReturnValue(0);
    tokens.resolveBearer.mockReturnValue({
      user: {
        id: "user-1",
        email: "user@example.com",
        password_hash: "",
        name: "",
        stripe_customer_id: null,
        card_verified: 1,
        email_verified: 1,
        banned: 0,
        created_at: 0,
      },
    });
  });

  it("records usage for a paid non-streaming response with cost", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            model: "anthropic/claude-sonnet-4.6",
            choices: [{ message: { content: "ok" } }],
            usage: { prompt_tokens: 2, completion_tokens: 1, cost: 0.00003 },
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        ),
      ),
    );

    const res = await POST(
      request({
        model: "anthropic/claude-sonnet-4.6",
        messages: [{ role: "user", content: "hi" }],
      }),
    );

    expect(res.status).toBe(200);
    expect(db.recordUsage).toHaveBeenCalledWith(
      "user-1",
      "anthropic/claude-sonnet-4.6",
      2,
      1,
      30,
    );
    expect(db.recordMeteringAlert).not.toHaveBeenCalled();
  });

  it("blocks paid non-streaming responses that lack usage.cost", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            model: "anthropic/claude-sonnet-4.6",
            choices: [{ message: { content: "ok" } }],
            usage: { prompt_tokens: 2, completion_tokens: 1 },
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        ),
      ),
    );

    const res = await POST(
      request({
        model: "anthropic/claude-sonnet-4.6",
        messages: [{ role: "user", content: "hi" }],
      }),
    );
    const json = (await res.json()) as { error: { code: string } };

    expect(res.status).toBe(502);
    expect(json.error.code).toBe("metering_unverified");
    expect(db.recordUsage).not.toHaveBeenCalled();
    expect(db.recordMeteringAlert).toHaveBeenCalledWith(
      "anthropic/claude-sonnet-4.6",
      "chat",
      "missing_cost",
      expect.any(String),
    );
  });

  it("blocks paid models with unresolved metering alerts before proxying", async () => {
    db.hasActiveMeteringAlert.mockReturnValue(true);
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);

    const res = await POST(
      request({
        model: "anthropic/claude-sonnet-4.6",
        messages: [{ role: "user", content: "hi" }],
      }),
    );
    const json = (await res.json()) as { error: { code: string } };

    expect(res.status).toBe(503);
    expect(json.error.code).toBe("metering_disabled");
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("allows free users to use only the selected GPT OSS 120B free model", async () => {
    db.getSubscription.mockReturnValue({ plan: "free", status: "active" });
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);

    const res = await POST(
      request({
        model: "meta-llama/llama-4-free:free",
        messages: [{ role: "user", content: "hi" }],
      }),
    );
    const json = (await res.json()) as { error: { code: string } };

    expect(res.status).toBe(403);
    expect(json.error.code).toBe("model_not_in_plan");
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
