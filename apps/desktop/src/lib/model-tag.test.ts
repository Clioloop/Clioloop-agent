import { describe, expect, it } from 'vitest'

import { managedModelTag } from './model-tag'

describe('managedModelTag', () => {
  it('tags the free managed model as (free)', () => {
    expect(managedModelTag('openai/gpt-oss-120b:free')).toBe('(free)')
  })

  it('tags :free OpenRouter variants as (free)', () => {
    expect(managedModelTag('tencent/hy3-preview:free')).toBe('(free)')
  })

  it('tags $0-priced models as (free) via pricing', () => {
    expect(managedModelTag('mystery-model', { free: true })).toBe('(free)')
  })

  it('tags bare ids as (open)', () => {
    expect(managedModelTag('qwen3-coder:480b')).toBe('(open)')
  })

  it('tags vendor/model ids as (openrouter)', () => {
    expect(managedModelTag('anthropic/claude-opus-4.8')).toBe('(openrouter)')
  })

  it('free wins over openrouter', () => {
    expect(managedModelTag('vendor/model', { free: true })).toBe('(free)')
  })
})
