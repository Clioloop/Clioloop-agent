import { beforeEach, describe, expect, it, vi } from 'vitest'

import { $paneStates } from '@/store/panes'

import { applyDesktopLayout, controlDesktopTour, focusDesktopPane, handleDesktopUiAction } from './desktop-ui-actions'

describe('desktop UI actions', () => {
  beforeEach(() => {
    document.body.innerHTML = '<main id="chat" aria-label="Chat"></main><button data-tour-id="models">Models</button>'
    $paneStates.set({
      'chat-sidebar': { open: true },
      'file-browser': { open: false },
      terminal: { open: false },
      'git-review': { open: false }
    })
  })

  it('applies useful pane presets through the real pane store', () => {
    applyDesktopLayout('coding')
    expect($paneStates.get()['file-browser']?.open).toBe(true)
    expect($paneStates.get().terminal?.open).toBe(true)

    applyDesktopLayout('focus')
    expect($paneStates.get()['chat-sidebar']?.open).toBe(false)
    expect($paneStates.get().terminal?.open).toBe(false)
  })

  it('reveals known panes and rejects unknown ones', async () => {
    expect(focusDesktopPane('files')).toBe(true)
    expect($paneStates.get()['file-browser']?.open).toBe(true)
    expect(focusDesktopPane('unknown')).toBe(false)
    await Promise.resolve()
  })

  it('shows a bounded guided-tour overlay and removes it', () => {
    const originalScrollIntoView = Element.prototype.scrollIntoView
    const scroller = vi.fn()
    Object.defineProperty(Element.prototype, 'scrollIntoView', { configurable: true, value: scroller })
    expect(controlDesktopTour({
      action: 'start',
      steps: [{ target: '[data-tour-id="models"]', title: 'Models', text: 'Choose a model.' }]
    })).toBe(true)
    expect(document.getElementById('clio-guided-tour-overlay')).not.toBeNull()
    expect(scroller).toHaveBeenCalled()

    expect(controlDesktopTour({ action: 'stop' })).toBe(true)
    expect(document.getElementById('clio-guided-tour-overlay')).toBeNull()

    if (originalScrollIntoView) {
      Object.defineProperty(Element.prototype, 'scrollIntoView', { configurable: true, value: originalScrollIntoView })
    } else {
      delete (Element.prototype as { scrollIntoView?: unknown }).scrollIntoView
    }
  })

  it('closes only the terminal view and emits reaction intent', () => {
    $paneStates.set({ ...$paneStates.get(), terminal: { open: true } })
    expect(handleDesktopUiAction('terminal.close', {})).toBe(true)
    expect($paneStates.get().terminal?.open).toBe(false)

    const listener = vi.fn()
    window.addEventListener('clio:message-react', listener)
    expect(handleDesktopUiAction('message.react', { message_id: 'm1', emoji: '✅' })).toBe(true)
    expect(listener).toHaveBeenCalledOnce()
    window.removeEventListener('clio:message-react', listener)
  })
})
