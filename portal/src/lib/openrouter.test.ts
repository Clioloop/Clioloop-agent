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
  MeteringError,
  modelAllowed,
  meteringBlocked,
  usageTapStream,
} from "./openrouter";
import { PLANS } from "./plans";

describe("OpenRouter metering", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    db.hasActiveMeteringAlert.mockReturnValue(false);
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

  it("fails safe and records an alert when paid usage.cost is missing", () => {
    expect(() =>
      meterUsage(
        "user-1",
        "anthropic/claude-sonnet-4.6",
        { prompt_tokens: 10, completion_tokens: 4 },
        { requirePositiveCost: true, path: "chat" },
      ),
    ).toThrow(MeteringError);

    expect(db.recordUsage).not.toHaveBeenCalled();
    expect(db.recordMeteringAlert).toHaveBeenCalledWith(
      "anthropic/claude-sonnet-4.6",
      "chat",
      "missing_cost",
      expect.stringContaining("prompt_tokens"),
    );
  });

  it("checks unresolved metering alerts before allowing future paid calls", () => {
    db.hasActiveMeteringAlert.mockReturnValue(true);

    expect(meteringBlocked("anthropic/claude-sonnet-4.6", "chat")).toBe(true);
    expect(db.hasActiveMeteringAlert).toHaveBeenCalledWith(
      "anthropic/claude-sonnet-4.6",
      "chat",
    );
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
