// Suffix tag for managed (Omni Loop Portal) models in the model pickers.
// Mirrors the Python `agent/fusion_engine.py::model_open_tag` rule so the CLI,
// Telegram, and desktop all label models the same way:
//   (free)       — the free model, ":free" OpenRouter variants, or $0 pricing
//   (open)       — BYO Ollama Cloud open-weight models (bare ids)
//   (openrouter) — paid OpenRouter models (vendor/model ids)
// `free` wins ties (a ":free" OpenRouter model is (free), not (openrouter)).

const FREE_MANAGED_MODEL = 'z-ai/glm-5.2'

export function managedModelTag(model: string, price?: { free?: boolean }): string {
  if (price?.free || model.endsWith(':free') || model === FREE_MANAGED_MODEL) {
    return '(free)'
  }

  return model.includes('/') ? '(openrouter)' : '(open)'
}
