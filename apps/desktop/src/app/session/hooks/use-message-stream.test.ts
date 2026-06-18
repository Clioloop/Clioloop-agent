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

  it('renders portal progress phases as persistent system message bodies', () => {
    expect(
      fusionStatusMessageBody({
        kind: 'fusion',
        phase: 'planning',
        text: 'Planning route...'
      })
    ).toBe('🔮 Planning route...')

    expect(
      fusionStatusMessageBody({
        kind: 'fusion',
        phase: 'working',
        text: 'Main model is working...'
      })
    ).toBe('🛠️ Main model is working...')

    expect(
      fusionStatusMessageBody({
        kind: 'fusion',
        phase: 'judge',
        text: 'Judge analyzing...'
      })
    ).toBe('⚖️ Judge analyzing...')

    expect(
      fusionStatusMessageBody({
        kind: 'fusion',
        phase: 'degraded',
        text: '⚠️ Review incomplete'
      })
    ).toBe('⚠️ Review incomplete')

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
