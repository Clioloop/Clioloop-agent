import { describe, expect, it } from 'vitest'

import { providerLabel } from './provider-label'

describe('providerLabel', () => {
  it('brands the managed subscription as Omni Loop Portal', () => {
    expect(providerLabel('managed')).toBe('Omni Loop Portal')
  })

  it('passes through unknown provider slugs unchanged', () => {
    expect(providerLabel('openrouter')).toBe('openrouter')
    expect(providerLabel('totally-custom')).toBe('totally-custom')
  })
})
