import { beforeEach, describe, expect, it, vi } from 'vitest'

import { $rightRailActiveTabId } from '@/store/layout'
import { $activeSessionId, $selectedStoredSessionId } from '@/store/session'

import { driveActivePreview, type PreviewRuntime, previewRuntimeKey, registerPreviewRuntime } from './preview-runtime'

function runtime(overrides: Partial<PreviewRuntime> = {}): PreviewRuntime {
  return {
    back: vi.fn(),
    focus: vi.fn(),
    forward: vi.fn(),
    run: vi.fn(async code => {
      if (code.includes('"kind":"locate"')) {
        return {
          acted: 'looking at button "Save"',
          point: { x: 20, y: 30 },
          success: true,
          typable: false
        }
      }

      return { delta: { same: 1 }, success: true }
    }),
    send: vi.fn(async () => undefined),
    ...overrides
  }
}

beforeEach(() => {
  $activeSessionId.set('session-1')
  $selectedStoredSessionId.set(null)
  $rightRailActiveTabId.set('preview')
})

describe('active preview drive', () => {
  it('inventories the selected preview tab through the registered runtime', async () => {
    const selected = runtime()
    const other = runtime()
    const unregisterSelected = registerPreviewRuntime(previewRuntimeKey('session-1', 'preview'), selected)
    const unregisterOther = registerPreviewRuntime(previewRuntimeKey('session-1', 'file:other'), other)

    try {
      expect(await driveActivePreview({ action: 'inventory', full: true, max: 20 })).toMatchObject({ success: true })
      expect(selected.run).toHaveBeenCalledOnce()
      expect(vi.mocked(selected.run).mock.calls[0]?.[0]).toContain('"kind":"elements"')
      expect(other.run).not.toHaveBeenCalled()
    } finally {
      unregisterSelected()
      unregisterOther()
    }
  })

  it('uses Electron input for a click and returns the compact post-action delta', async () => {
    const selected = runtime()
    const unregister = registerPreviewRuntime(previewRuntimeKey('session-1', 'preview'), selected)

    try {
      const result = await driveActivePreview({ action: 'click', ref: 'btn-save' })

      expect(result).toMatchObject({ acted: 'clicked button "Save"', delta: { same: 1 }, success: true })
      expect(selected.focus).toHaveBeenCalledOnce()
      expect(selected.send).toHaveBeenCalled()
      expect(vi.mocked(selected.send).mock.calls.some(([event]) => event.type === 'mouseDown')).toBe(true)
    } finally {
      unregister()
    }
  })

  it('fails explicitly rather than substituting synthetic input', async () => {
    const selected = runtime({ send: vi.fn(async () => Promise.reject(new Error('input unavailable'))) })
    const unregister = registerPreviewRuntime(previewRuntimeKey('session-1', 'preview'), selected)

    try {
      const result = await driveActivePreview({ action: 'click', ref: 'btn-save' })

      expect(result.success).toBe(false)
      expect(result.error).toContain('Trusted preview input failed')
      expect(result.error).toContain('input unavailable')
    } finally {
      unregister()
    }
  })

  it('refuses to act when the active pane has no web runtime', async () => {
    $rightRailActiveTabId.set('file:source-only')

    expect(await driveActivePreview({ action: 'click', ref: 'btn-save' })).toEqual({
      error: 'No active web preview can receive trusted input. Open a web preview and select its tab first.',
      success: false
    })
  })
})
