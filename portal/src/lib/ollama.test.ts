import { describe, expect, it } from "vitest";
import {
  FREE_OLLAMA_MODEL,
  isOllamaModel,
  modelAllowedForPlan,
  ollamaCostMicros,
} from "./ollama";

describe("ollama model classification", () => {
  it("treats bare ids as Ollama and vendor/model ids as OpenRouter", () => {
    expect(isOllamaModel("kimi-k2.7-code")).toBe(true);
    expect(isOllamaModel("qwen3-coder:480b")).toBe(true);
    expect(isOllamaModel("gpt-oss:120b")).toBe(true);
    expect(isOllamaModel("anthropic/claude-opus-4.8")).toBe(false);
    expect(isOllamaModel("moonshotai/kimi-k2.5")).toBe(false);
    expect(isOllamaModel("")).toBe(false);
  });
});

describe("modelAllowedForPlan", () => {
  it("free → only the one free model", () => {
    expect(modelAllowedForPlan("free", FREE_OLLAMA_MODEL)).toBe(true);
    expect(modelAllowedForPlan("free", "qwen3-coder:480b")).toBe(false);
    expect(modelAllowedForPlan("free", "anthropic/claude-opus-4.8")).toBe(false);
  });
  it("pro → any Ollama model, no OpenRouter", () => {
    expect(modelAllowedForPlan("pro", "qwen3-coder:480b")).toBe(true);
    expect(modelAllowedForPlan("pro", FREE_OLLAMA_MODEL)).toBe(true);
    expect(modelAllowedForPlan("pro", "anthropic/claude-opus-4.8")).toBe(false);
  });
  it("max / max20x → anything", () => {
    expect(modelAllowedForPlan("max", "anthropic/claude-opus-4.8")).toBe(true);
    expect(modelAllowedForPlan("max", "qwen3-coder:480b")).toBe(true);
    expect(modelAllowedForPlan("max20x", "openai/gpt-5.5")).toBe(true);
  });
});

describe("ollamaCostMicros", () => {
  it("is 0 for a zero price (free model within the allotment)", () => {
    expect(
      ollamaCostMicros({ prompt_tokens: 10_000, completion_tokens: 5_000 }, { prompt: 0, completion: 0 }),
    ).toBe(0);
  });
  it("computes tokens × per-token price in micros", () => {
    // $0.20/Mtok in, $0.80/Mtok out → per-token 0.0000002 / 0.0000008
    const micros = ollamaCostMicros(
      { prompt_tokens: 1_000_000, completion_tokens: 1_000_000 },
      { prompt: 0.0000002, completion: 0.0000008 },
    );
    // (1e6*2e-7 + 1e6*8e-7) = 0.2 + 0.8 = $1.00 → 1_000_000 micros
    expect(micros).toBe(1_000_000);
  });
  it("returns 0 when usage is missing", () => {
    expect(ollamaCostMicros(undefined, { prompt: 0.01, completion: 0.01 })).toBe(0);
  });
});
