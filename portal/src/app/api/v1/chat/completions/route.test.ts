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
    globalThis.__olpModelCache = undefined;
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
      vi.fn(
        async () =>
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

  it("still bills (catalog fallback) a paid response that lacks usage.cost — no block", async () => {
    globalThis.__olpModelCache = {
      at: Date.now(),
      data: [
        {
          id: "anthropic/claude-sonnet-4.6",
          pricing: { prompt: "0.000003", completion: "0.000015" },
        },
      ],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              model: "anthropic/claude-sonnet-4.6",
              choices: [{ message: { content: "ok" } }],
              usage: { prompt_tokens: 1000, completion_tokens: 500 },
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
    // 1000*0.000003 + 500*0.000015 = 0.0105 USD → 10500 micros, charged from catalog.
    expect(db.recordUsage).toHaveBeenCalledWith(
      "user-1",
      "anthropic/claude-sonnet-4.6",
      1000,
      500,
      10500,
    );
  });

  it("does not block a model that has an unresolved metering alert (self-heals)", async () => {
    db.hasActiveMeteringAlert.mockReturnValue(true);
    const fetchSpy = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            model: "anthropic/claude-sonnet-4.6",
            choices: [{ message: { content: "ok" } }],
            usage: { prompt_tokens: 2, completion_tokens: 1, cost: 0.00003 },
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        ),
    );
    vi.stubGlobal("fetch", fetchSpy);

    const res = await POST(
      request({
        model: "anthropic/claude-sonnet-4.6",
        messages: [{ role: "user", content: "hi" }],
      }),
    );

    expect(res.status).toBe(200);
    expect(fetchSpy).toHaveBeenCalled();
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
