import { describe, expect, it, vi } from "vitest";
import { FREE_OPENROUTER_MODEL, modelAllowedForPlan } from "./model-policy";

describe("modelAllowedForPlan", () => {
  it("free → only the one free model", () => {
    expect(modelAllowedForPlan("free", FREE_OPENROUTER_MODEL)).toBe(true);
    expect(modelAllowedForPlan("free", "z-ai/glm-5.2")).toBe(false);
    expect(modelAllowedForPlan("free", "qwen/qwen3-coder")).toBe(false);
    expect(modelAllowedForPlan("free", "anthropic/claude-opus-4.8")).toBe(false);
  });
  it("paid tiers → any OpenRouter model", () => {
    for (const plan of ["pro", "max", "max20x"] as const) {
      expect(modelAllowedForPlan(plan, "anthropic/claude-opus-4.8")).toBe(true);
      expect(modelAllowedForPlan(plan, "openai/gpt-5.5")).toBe(true);
      expect(modelAllowedForPlan(plan, FREE_OPENROUTER_MODEL)).toBe(true);
    }
  });
});

describe("FREE_OPENROUTER_MODEL", () => {
  it("defaults to DeepSeek V4 Pro (promotional free model)", () => {
    expect(FREE_OPENROUTER_MODEL).toBe("deepseek/deepseek-v4-pro");
  });

  it("is a valid OpenRouter model id", () => {
    expect(FREE_OPENROUTER_MODEL).toContain("/");
  });

  it("ignores the obsolete GLM 5.2 environment override", async () => {
    const previous = process.env.FREE_OPENROUTER_MODEL;
    try {
      process.env.FREE_OPENROUTER_MODEL = "z-ai/glm-5.2";
      vi.resetModules();
      const policy = await import("./model-policy");
      expect(policy.FREE_OPENROUTER_MODEL).toBe("deepseek/deepseek-v4-pro");
    } finally {
      if (previous === undefined) delete process.env.FREE_OPENROUTER_MODEL;
      else process.env.FREE_OPENROUTER_MODEL = previous;
      vi.resetModules();
    }
  });
});

describe("portal inference upstream selection", () => {
  it("always routes to OpenRouter", async () => {
    vi.resetModules();
    process.env.OPENROUTER_API_KEY = "openrouter-test-key";

    const route = await import("./inference-upstream");

    expect(route.selectInferenceUpstream()).toMatchObject({
      kind: "openrouter",
      key: "openrouter-test-key",
    });
  });
});
