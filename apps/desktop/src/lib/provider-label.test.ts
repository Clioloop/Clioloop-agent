import { describe, expect, it } from 'vitest'

import {
  compareOmniFirst,
  isOmniProvider,
  OMNI_PROVIDER_BADGE,
  OMNI_PROVIDER_DESCRIPTION,
  OMNI_PROVIDER_LABEL,
  providerLabel
} from './provider-label'

describe('providerLabel', () => {
  it('brands the managed subscription as Omni Loop Portal Subscription', () => {
    expect(providerLabel('managed')).toBe(OMNI_PROVIDER_LABEL)
  })

  it('passes through unknown provider slugs unchanged', () => {
    expect(providerLabel('openrouter')).toBe('openrouter')
    expect(providerLabel('totally-custom')).toBe('totally-custom')
  })

  it('exposes Omni display metadata for picker rows', () => {
    expect(isOmniProvider('managed')).toBe(true)
    expect(OMNI_PROVIDER_BADGE).toBe('Recommended')
    expect(OMNI_PROVIDER_DESCRIPTION).toContain('only way to use Model Fusion')
  })

  it('sorts Omni first while preserving other provider order', () => {
    const rows = [{ slug: 'openai-codex' }, { slug: 'managed' }, { slug: 'anthropic' }]

    expect([...rows].sort(compareOmniFirst).map(row => row.slug)).toEqual([
      'managed',
      'openai-codex',
      'anthropic'
    ])
  })
})
