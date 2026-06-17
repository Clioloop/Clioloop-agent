import { describe, expect, it, vi } from "vitest";
import { FREE_OPENROUTER_MODEL, modelAllowedForPlan } from "./model-policy";

describe("modelAllowedForPlan", () => {
  it("free → only the one free model", () => {
    expect(modelAllowedForPlan("free", FREE_OPENROUTER_MODEL)).toBe(true);
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
  it("defaults to the selected GPT OSS 120B free model", () => {
    expect(FREE_OPENROUTER_MODEL).toBe("openai/gpt-oss-120b:free");
  });

  it("is an OpenRouter :free id", () => {
    expect(FREE_OPENROUTER_MODEL.endsWith(":free")).toBe(true);
    expect(FREE_OPENROUTER_MODEL).toContain("/");
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
