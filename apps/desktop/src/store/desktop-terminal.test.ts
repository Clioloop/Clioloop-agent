import { afterEach, describe, expect, it, vi } from 'vitest'

import { closeDesktopTerminal, readDesktopTerminal, registerDesktopTerminalBridge } from './desktop-terminal'

describe('desktop terminal bridge', () => {
  let dispose: (() => void) | null = null

  afterEach(() => {
    dispose?.()
    dispose = null
  })

  it('fails closed without a mounted terminal', () => {
    expect(readDesktopTerminal()).toMatchObject({ available: false, text: '' })
    expect(closeDesktopTerminal()).toBe(false)
  })

  it('routes bounded reads and view closes to the mounted terminal', () => {
    const read = vi.fn(() => ({ available: true, text: 'hello', count: 5 }))
    const close = vi.fn(() => true)
    dispose = registerDesktopTerminalBridge({ read, close })

    expect(readDesktopTerminal(4, 9)).toMatchObject({ text: 'hello' })
    expect(read).toHaveBeenCalledWith(4, 9)
    expect(closeDesktopTerminal('term-1')).toBe(true)
    expect(close).toHaveBeenCalledWith('term-1')
  })
})
