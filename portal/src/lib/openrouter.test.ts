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

  it("records a 1µ floor when both cost and catalog price are unavailable", () => {
    const result = meterUsage(
      "user-1",
      "some/unknown-model",
      { prompt_tokens: 10, completion_tokens: 4 },
      { requirePositiveCost: true, path: "chat" },
    );
    expect(result).toEqual({ recorded: true, costMicros: 1 });
    expect(db.recordUsage).toHaveBeenCalledWith("user-1", "some/unknown-model", 10, 4, 1);
  });

  it("records zero for free models/tier without throwing", () => {
    const result = meterUsage(
      "user-1",
      "openai/gpt-oss-120b:free",
      { prompt_tokens: 5, completion_tokens: 2 },
      { requirePositiveCost: false },
    );
    expect(result).toEqual({ recorded: true, costMicros: 0 });
    expect(db.recordUsage).toHaveBeenCalledWith("user-1", "openai/gpt-oss-120b:free", 5, 2, 0);
  });

  it("modelPriceMicros computes from the cached catalog", () => {
    globalThis.__olpModelCache = {
      at: Date.now(),
      data: [{ id: "m", pricing: { prompt: "0.000001", completion: "0.000002" } }],
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
    const stream = usageTapStream(onUsage, "anthropic/claude-sonnet-4.6", onMissing);
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
    const stream = usageTapStream(onUsage, "anthropic/claude-sonnet-4.6", onMissing);
    const writer = stream.writable.getWriter();
    const reader = stream.readable.getReader();
    const drain = (async () => {
      while (!(await reader.read()).done) {
        // drain passthrough stream
      }
    })();

    await writer.write(new TextEncoder().encode('data: {"choices":[{"delta":{"content":"hi"}}]}\n\n'));
    await writer.close();
    await drain;

    expect(onUsage).not.toHaveBeenCalled();
    expect(onMissing).toHaveBeenCalledWith("anthropic/claude-sonnet-4.6");
  });
});

describe("OpenRouter catalog filtering", () => {
  it("keeps text-output models and excludes explicit non-text outputs", () => {
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
    expect(isTextOutputModel({ id: "legacy/model" })).toBe(true);
  });
});

describe("legacy OpenRouter plan helper", () => {
  it("keeps free-only plans limited to the selected free model", () => {
    expect(modelAllowed(PLANS.free, "openai/gpt-oss-120b:free")).toBe(true);
    expect(modelAllowed(PLANS.free, "meta-llama/llama-4-free:free")).toBe(false);
    expect(modelAllowed(PLANS.pro, "meta-llama/llama-4-free:free")).toBe(true);
  });
});
