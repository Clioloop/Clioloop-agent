import { beforeEach, describe, expect, it, vi } from "vitest";

const db = vi.hoisted(() => ({
  getSubscription: vi.fn(),
  hasActiveMeteringAlert: vi.fn(),
  monthUsageMicros: vi.fn(),
  recordMeteringAlert: vi.fn(),
  recordUsage: vi.fn(),
}));

vi.mock("./db", () => db);

import {
  isTextOutputModel,
  meterUsage,
  modelPriceMicros,
  modelAllowed,
  meteringBlocked,
  usageTapStream,
} from "./openrouter";
import { PLANS } from "./plans";

describe("OpenRouter metering", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    db.hasActiveMeteringAlert.mockReturnValue(false);
    globalThis.__olpModelCache = undefined;
    delete process.env.METERING_UNKNOWN_PAID_PROMPT_PRICE_USD;
    delete process.env.METERING_UNKNOWN_PAID_COMPLETION_PRICE_USD;
    delete process.env.METERING_MISSING_USAGE_PROMPT_TOKEN_FLOOR;
    delete process.env.METERING_MISSING_USAGE_COMPLETION_TOKEN_FLOOR;
  });

  it("records OpenRouter cost in credit micros", () => {
    const result = meterUsage(
      "user-1",
      "anthropic/claude-sonnet-4.6",
      { prompt_tokens: 10, completion_tokens: 4, cost: 0.00014 },
      { requirePositiveCost: true },
    );

    expect(result).toEqual({ recorded: true, costMicros: 140 });
    expect(db.recordUsage).toHaveBeenCalledWith(
      "user-1",
      "anthropic/claude-sonnet-4.6",
      10,
      4,
      140,
    );
    expect(db.recordMeteringAlert).not.toHaveBeenCalled();
  });

  it("falls back to the catalog price when paid usage.cost is missing (no throw)", () => {
    globalThis.__olpModelCache = {
      at: Date.now(),
      data: [
        {
          id: "anthropic/claude-sonnet-4.6",
          pricing: { prompt: "0.000003", completion: "0.000015" },
        },
      ],
    };
    const result = meterUsage(
      "user-1",
      "anthropic/claude-sonnet-4.6",
      { prompt_tokens: 1000, completion_tokens: 500 },
      { requirePositiveCost: true, path: "chat" },
    );
    // 1000*0.000003 + 500*0.000015 = 0.0105 USD → 10500 micros
    expect(result).toEqual({ recorded: true, costMicros: 10500 });
    expect(db.recordUsage).toHaveBeenCalledWith(
      "user-1",
      "anthropic/claude-sonnet-4.6",
      1000,
      500,
      10500,
    );
  });

  it("uses catalog pricing for dated model aliases returned by the upstream", () => {
    globalThis.__olpModelCache = {
      at: Date.now(),
      data: [
        {
          id: "z-ai/glm-5.2",
          pricing: { prompt: "0.0000014", completion: "0.0000044" },
        },
      ],
    };
    const result = meterUsage(
      "user-1",
      "z-ai/glm-5.2-20260616",
      { prompt_tokens: 13, completion_tokens: 6 },
      { requirePositiveCost: true, path: "chat" },
    );
    expect(result).toEqual({ recorded: true, costMicros: 45 });
    expect(db.recordUsage).toHaveBeenCalledWith(
      "user-1",
      "z-ai/glm-5.2-20260616",
      13,
      6,
      45,
    );
    expect(db.recordMeteringAlert).not.toHaveBeenCalled();
  });

  it("records a conservative alerting charge when both cost and catalog price are unavailable", () => {
    const result = meterUsage(
      "user-1",
      "some/unknown-model",
      { prompt_tokens: 10, completion_tokens: 4 },
      { requirePositiveCost: true, path: "chat" },
    );
    expect(result).toEqual({ recorded: true, costMicros: 600 });
    expect(db.recordUsage).toHaveBeenCalledWith(
      "user-1",
      "some/unknown-model",
      10,
      4,
      600,
    );
    expect(db.recordMeteringAlert).toHaveBeenCalledWith(
      "some/unknown-model",
      "chat",
      "missing_paid_model_price",
      "10/4 tok charged 600µ conservative fallback",
    );
  });

  it("uses missing-usage token floors instead of a symbolic floor for paid anomalies", () => {
    process.env.METERING_MISSING_USAGE_PROMPT_TOKEN_FLOOR = "100";
    process.env.METERING_MISSING_USAGE_COMPLETION_TOKEN_FLOOR = "50";
    globalThis.__olpModelCache = {
      at: Date.now(),
      data: [
        {
          id: "anthropic/claude-sonnet-4.6",
          pricing: { prompt: "0.000003", completion: "0.000015" },
        },
      ],
    };

    const result = meterUsage(
      "user-1",
      "anthropic/claude-sonnet-4.6",
      undefined,
      { requirePositiveCost: true, path: "chat" },
    );

    expect(result).toEqual({ recorded: true, costMicros: 1050 });
    expect(db.recordUsage).toHaveBeenCalledWith(
      "user-1",
      "anthropic/claude-sonnet-4.6",
      0,
      0,
      1050,
    );
  });

  it("records zero for free models/tier without throwing", () => {
    const result = meterUsage(
      "user-1",
      "openai/gpt-oss-120b:free",
      { prompt_tokens: 5, completion_tokens: 2 },
      { requirePositiveCost: false },
    );
    expect(result).toEqual({ recorded: true, costMicros: 0 });
    expect(db.recordUsage).toHaveBeenCalledWith(
      "user-1",
      "openai/gpt-oss-120b:free",
      5,
      2,
      0,
    );
  });

  it("records zero for promotional free model even when upstream reports a cost", () => {
    // DeepSeek V4 Pro is paid on OpenRouter, but when used as the promotional
    // free model Clioloop absorbs the cost (requirePositiveCost: false).
    const result = meterUsage(
      "user-1",
      "deepseek/deepseek-v4-pro",
      { prompt_tokens: 100, completion_tokens: 50, cost: 0.00037 },
      { requirePositiveCost: false },
    );
    expect(result).toEqual({ recorded: true, costMicros: 0 });
    expect(db.recordUsage).toHaveBeenCalledWith(
      "user-1",
      "deepseek/deepseek-v4-pro",
      100,
      50,
      0,
    );
  });

  it("modelPriceMicros computes from the cached catalog", () => {
    globalThis.__olpModelCache = {
      at: Date.now(),
      data: [
        { id: "m", pricing: { prompt: "0.000001", completion: "0.000002" } },
      ],
    };
    expect(modelPriceMicros("m", 1000, 1000)).toBe(3000); // (0.001 + 0.002) USD → micros
    expect(modelPriceMicros("unknown", 1000, 1000)).toBeNull();
  });

  it("meteringBlocked is always false — metering self-heals", () => {
    db.hasActiveMeteringAlert.mockReturnValue(true);
    expect(meteringBlocked("anything", "chat")).toBe(false);
  });

  it("captures streaming final usage exactly once", async () => {
    const onUsage = vi.fn();
    const onMissing = vi.fn();
    const stream = usageTapStream(
      onUsage,
      "anthropic/claude-sonnet-4.6",
      onMissing,
    );
    const writer = stream.writable.getWriter();
    const reader = stream.readable.getReader();
    const drain = (async () => {
      while (!(await reader.read()).done) {
        // drain passthrough stream
      }
    })();

    await writer.write(
      new TextEncoder().encode(
        'data: {"model":"anthropic/claude-sonnet-4.6","usage":{"prompt_tokens":2,"completion_tokens":1,"cost":0.00003}}\n\n',
      ),
    );
    await writer.close();
    await drain;

    expect(onUsage).toHaveBeenCalledTimes(1);
    expect(onUsage).toHaveBeenCalledWith(
      { prompt_tokens: 2, completion_tokens: 1, cost: 0.00003 },
      "anthropic/claude-sonnet-4.6",
    );
    expect(onMissing).not.toHaveBeenCalled();
  });

  it("alerts when a stream ends without usage", async () => {
    const onUsage = vi.fn();
    const onMissing = vi.fn();
    const stream = usageTapStream(
      onUsage,
      "anthropic/claude-sonnet-4.6",
      onMissing,
    );
    const writer = stream.writable.getWriter();
    const reader = stream.readable.getReader();
    const drain = (async () => {
      while (!(await reader.read()).done) {
        // drain passthrough stream
      }
    })();

    await writer.write(
      new TextEncoder().encode(
        'data: {"choices":[{"delta":{"content":"hi"}}]}\n\n',
      ),
    );
    await writer.close();
    await drain;

    expect(onUsage).not.toHaveBeenCalled();
    expect(onMissing).toHaveBeenCalledWith("anthropic/claude-sonnet-4.6");
  });
});

describe("OpenRouter catalog filtering", () => {
  it("keeps plain text-output models and excludes non-chat outputs", () => {
    expect(
      isTextOutputModel({
        id: "text/model",
        architecture: { output_modalities: ["text"] },
      }),
    ).toBe(true);
    expect(
      isTextOutputModel({
        id: "image/model",
        architecture: { output_modalities: ["image"] },
      }),
    ).toBe(false);
    expect(
      isTextOutputModel({
        id: "audio/model",
        architecture: { output_modalities: ["text", "audio"] },
      }),
    ).toBe(false);
    expect(isTextOutputModel({ id: "legacy/model" })).toBe(true);
  });

  it("excludes known unsafe normal-chat catalog entries", () => {
    expect(
      isTextOutputModel({
        id: "openrouter/fusion",
        architecture: { output_modalities: ["text"] },
      }),
    ).toBe(false);
    expect(
      isTextOutputModel({
        id: "arcee-ai/virtuoso-large",
        architecture: { output_modalities: ["text"] },
      }),
    ).toBe(false);
    expect(
      isTextOutputModel({
        id: "openai/o3-deep-research",
        architecture: { output_modalities: ["text"] },
      }),
    ).toBe(false);
  });
});

describe("legacy OpenRouter plan helper", () => {
  it("keeps free-only plans limited to the selected free model", () => {
    expect(modelAllowed(PLANS.free, "deepseek/deepseek-v4-pro")).toBe(true);
    expect(modelAllowed(PLANS.free, "z-ai/glm-5.2")).toBe(false);
    expect(modelAllowed(PLANS.free, "meta-llama/llama-4-free:free")).toBe(
      false,
    );
    expect(modelAllowed(PLANS.pro, "meta-llama/llama-4-free:free")).toBe(true);
  });
});
