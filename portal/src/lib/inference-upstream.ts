import { OPENROUTER_BASE, openRouterKey } from "./openrouter";

export interface InferenceUpstream {
  kind: "openrouter";
  base: string;
  key: string;
}

/** All inference routes through OpenRouter. */
export function selectInferenceUpstream(): InferenceUpstream {
  return { kind: "openrouter", base: OPENROUTER_BASE, key: openRouterKey() };
}
