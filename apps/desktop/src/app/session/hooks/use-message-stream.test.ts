import { describe, expect, it } from 'vitest'

import { fusionStatusMessageBody } from './use-message-stream'

describe('fusionStatusMessageBody', () => {
  it('renders the reset reminder as a persistent system message body', () => {
    const reminder = '🔮 Fusion run complete. Start a fresh session before your next Fusion run (/new or /reset).'

    expect(
      fusionStatusMessageBody({
        kind: 'fusion',
        phase: 'reset_reminder',
        text: reminder
      })
    ).toBe(reminder)
  })

  it('keeps planning transient and preserves reviewer note formatting', () => {
    expect(
      fusionStatusMessageBody({
        kind: 'fusion',
        phase: 'planning',
        text: 'Planning route...'
      })
    ).toBeNull()

    expect(
      fusionStatusMessageBody({
        detail: 'Missing edge case X.',
        kind: 'fusion',
        phase: 'critique',
        text: 'Reviewer 1'
      })
    ).toBe('📝 Reviewer 1\n\nMissing edge case X.')
  })
})
