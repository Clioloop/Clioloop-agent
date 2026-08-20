import { act, cleanup, render, waitFor } from '@testing-library/react'
import { useEffect, useRef } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { assistantTextPart, type ChatMessage } from '@/lib/chat-messages'
import {
  $previewTarget,
  clearSessionPreviewRegistry,
  type PreviewTarget,
  registerSessionPreview
} from '@/store/preview'
import { $currentCwd, $messages } from '@/store/session'
import type { RpcEvent } from '@/types/clio'

import { usePreviewRouting } from './use-preview-routing'

function assistantMessage(id: string, text: string): ChatMessage {
  return {
    id,
    parts: [assistantTextPart(text)],
    role: 'assistant'
  }
}

function previewTarget(source: string): PreviewTarget {
  const isUrl = /^https?:\/\//i.test(source)

  return {
    kind: isUrl ? 'url' : 'file',
    label: source,
    path: isUrl ? undefined : source,
    previewKind: isUrl ? undefined : 'html',
    source,
    url: isUrl ? source : `file://${source}`
  }
}

let handleEvent: (event: RpcEvent) => void = () => undefined

function PreviewRoutingHarness({
  onEvent,
  requestGateway = vi.fn()
}: {
  onEvent: (handler: (event: RpcEvent) => void) => void
  requestGateway?: <T = unknown>(method: string, params?: Record<string, unknown>) => Promise<T>
}) {
  const activeSessionIdRef = useRef<string | null>('session-1')

  const routing = usePreviewRouting({
    activeSessionIdRef,
    baseHandleGatewayEvent: vi.fn(),
    currentCwd: '/work',
    currentView: 'chat',
    requestGateway,
    routedSessionId: 'session-1',
    selectedStoredSessionId: null
  })

  useEffect(() => {
    onEvent(routing.handleDesktopGatewayEvent)
  }, [onEvent, routing.handleDesktopGatewayEvent])

  return null
}

describe('usePreviewRouting', () => {
  beforeEach(() => {
    $currentCwd.set('/work')
    $messages.set([])
    $previewTarget.set(null)
    window.localStorage.clear()
    clearSessionPreviewRegistry()
    handleEvent = () => undefined

    Object.defineProperty(window, 'clioDesktop', {
      configurable: true,
      value: {
        normalizePreviewTarget: vi.fn(async (target: string) => previewTarget(target))
      }
    })
  })

  afterEach(() => {
    cleanup()
    $messages.set([])
    $previewTarget.set(null)
    window.localStorage.clear()
    clearSessionPreviewRegistry()
    vi.restoreAllMocks()
  })

  it('opens the active session preview from the registry', async () => {
    const target = previewTarget('/work/demo.html')

    registerSessionPreview('session-1', target, 'tool-result')
    render(
      <PreviewRoutingHarness
        onEvent={handler => {
          handleEvent = handler
        }}
      />
    )

    await waitFor(() => {
      expect($previewTarget.get()).toEqual({ ...target, renderMode: 'preview' })
    })
  })

  it('does not infer previews from assistant prose', async () => {
    render(
      <PreviewRoutingHarness
        onEvent={handler => {
          handleEvent = handler
        }}
      />
    )

    act(() => {
      $messages.set([
        assistantMessage('a1', 'Preview: http://localhost:5173/'),
        assistantMessage('a2', 'Open /work/demo.html')
      ])
    })

    expect($previewTarget.get()).toBeNull()
    expect(window.clioDesktop.normalizePreviewTarget).not.toHaveBeenCalled()
  })

  it('registers structured tool-result preview targets', async () => {
    render(
      <PreviewRoutingHarness
        onEvent={handler => {
          handleEvent = handler
        }}
      />
    )

    act(() =>
      handleEvent({
        payload: { path: './dist/index.html' },
        session_id: 'session-1',
        type: 'tool.complete'
      })
    )

    await waitFor(() => {
      expect($previewTarget.get()?.source).toBe('./dist/index.html')
    })

    expect(window.localStorage.getItem('clio.desktop.sessionPreviews.v1')).toContain('./dist/index.html')
  })

  it('registers html previews from edit inline diffs', async () => {
    render(
      <PreviewRoutingHarness
        onEvent={handler => {
          handleEvent = handler
        }}
      />
    )

    act(() =>
      handleEvent({
        payload: { inline_diff: '\u001b[38;2;218;165;32ma/preview-demo.html -> b/preview-demo.html\u001b[0m\n' },
        session_id: 'session-1',
        type: 'tool.complete'
      })
    )

    await waitFor(() => {
      expect($previewTarget.get()?.source).toBe('preview-demo.html')
    })
  })

  it('handles explicit desktop preview open and close events', async () => {
    render(
      <PreviewRoutingHarness
        onEvent={handler => {
          handleEvent = handler
        }}
      />
    )

    act(() => handleEvent({ type: 'preview.open', session_id: 'session-1', payload: { url: 'example.com', label: 'Example' } }))
    await waitFor(() => expect($previewTarget.get()?.label).toBe('Example'))

    act(() => handleEvent({ type: 'preview.close', session_id: 'session-1', payload: { url: 'example.com' } }))
    await waitFor(() => expect($previewTarget.get()).toBeNull())
  })

  it('answers bounded desktop preview read requests', async () => {
    const requestGatewayMock = vi.fn(async (_method: string, _params?: Record<string, unknown>) => ({ status: 'ok' }))

    const requestGateway = requestGatewayMock as unknown as <T = unknown>(
      method: string,
      params?: Record<string, unknown>
    ) => Promise<T>

    const target = previewTarget('https://example.com')
    registerSessionPreview('session-1', target, 'tool-result')

    render(
      <PreviewRoutingHarness
        onEvent={handler => {
          handleEvent = handler
        }}
        requestGateway={requestGateway}
      />
    )

    act(() => handleEvent({
      type: 'desktop_ui.request',
      session_id: 'session-1',
      payload: { request_id: 'req-1', action: 'preview.read', payload: { start: 0, count: 100 } }
    }))

    await waitFor(() => {
      expect(requestGatewayMock).toHaveBeenCalledWith('desktop_ui.respond', expect.objectContaining({ request_id: 'req-1' }))
    })
    const response = requestGatewayMock.mock.calls[0]?.[1] as unknown as { result: string }
    expect(JSON.parse(response.result)).toMatchObject({ open: true, url: 'https://example.com' })
  })
})
