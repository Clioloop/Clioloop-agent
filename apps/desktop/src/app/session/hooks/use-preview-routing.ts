import { useStore } from '@nanostores/react'
import { type MutableRefObject, useCallback, useEffect } from 'react'

import { annotateActivePreview, driveActivePreview } from '@/app/chat/right-rail/preview-runtime'
import { handleDesktopUiAction } from '@/lib/desktop-ui-actions'
import { gatewayEventCompletedFileDiff } from '@/lib/gateway-events'
import { readDesktopTerminal } from '@/store/desktop-terminal'
import {
  $filePreviewTarget,
  $previewTarget,
  $sessionPreviewRegistry,
  beginPreviewServerRestart,
  closePreviewByUrl,
  closeRightRail,
  completePreviewServerRestart,
  getSessionPreviewRecord,
  type PreviewTarget,
  progressPreviewServerRestart,
  requestPreviewReload,
  setPreviewTarget,
  setSessionPreviewTarget
} from '@/store/preview'
import { $currentCwd } from '@/store/session'
import type { RpcEvent } from '@/types/clio'

type EventHandler = (event: RpcEvent) => void

interface PreviewRoutingOptions {
  activeSessionIdRef: MutableRefObject<string | null>
  baseHandleGatewayEvent: EventHandler
  currentCwd: string
  currentView: string
  requestGateway: <T = unknown>(method: string, params?: Record<string, unknown>) => Promise<T>
  routedSessionId: string | null
  selectedStoredSessionId: string | null
}

function asRecord(payload: unknown): Record<string, unknown> {
  return payload && typeof payload === 'object' ? (payload as Record<string, unknown>) : {}
}

function activePreviewSessionId(
  activeSessionIdRef: MutableRefObject<string | null>,
  routedSessionId: string | null,
  selectedStoredSessionId: string | null
): string {
  return selectedStoredSessionId || routedSessionId || activeSessionIdRef.current || ''
}

function looksLikePreviewTarget(value: string): boolean {
  return /^https?:\/\//i.test(value) || /^file:\/\//i.test(value) || /^(?:\/|\.{1,2}\/|~\/).+/.test(value)
}

function stripAnsi(value: string): string {
  return value.replace(new RegExp(`${String.fromCharCode(27)}\\[[0-9;]*m`, 'g'), '')
}

function htmlPathFromInlineDiff(value: string): string {
  const cleaned = stripAnsi(value).replace(/^\s*┊\s*review diff\s*\n/i, '')

  for (const match of cleaned.matchAll(/(?:^|\s)(?:[ab]\/)?([^\s]+\.html?)(?=\s|$)/gi)) {
    const candidate = match[1]?.trim()

    if (candidate) {
      return candidate
    }
  }

  return ''
}

function structuredPreviewCandidate(payload: unknown): string {
  const record = asRecord(payload)
  const fields = ['url', 'target', 'path', 'file', 'filepath', 'preview']

  for (const field of fields) {
    const value = record[field]

    if (typeof value === 'string') {
      const target = value.trim()

      if (target && looksLikePreviewTarget(target)) {
        return target
      }
    }
  }

  const inlineDiff = record.inline_diff

  if (typeof inlineDiff === 'string') {
    return htmlPathFromInlineDiff(inlineDiff)
  }

  return ''
}

export function desktopUiPreviewSnapshot(start = 0, count = 12_000): Record<string, unknown> {
  const target = $filePreviewTarget.get() ?? $previewTarget.get()
  const offset = Math.max(0, Math.floor(start))
  const limit = Math.max(1, Math.min(Math.floor(count), 20_000))

  if (!target) {
    return { open: false, start: offset, count: 0, text: '' }
  }

  // File/source text and remote Browser text are owned by their dedicated
  // panes.  The stable snapshot always reports identity; pane implementations
  // can add renderedText without changing the tool protocol.
  const renderedText = typeof (target as PreviewTarget & { renderedText?: unknown }).renderedText === 'string'
    ? String((target as PreviewTarget & { renderedText?: string }).renderedText)
    : ''

  const text = renderedText.slice(offset, offset + limit)

  return {
    open: true,
    kind: target.kind,
    label: target.label,
    mime_type: target.mimeType ?? null,
    path: target.path ?? null,
    source: target.source,
    url: target.url,
    start: offset,
    count: text.length,
    text,
    has_more: offset + text.length < renderedText.length
  }
}

export function desktopUiTourTargets(root: ParentNode = document): Array<{ target: string; label: string }> {
  const seen = new Set<string>()
  const targets: Array<{ target: string; label: string }> = []
  const nodes = root.querySelectorAll<HTMLElement>('[data-tour-id], [aria-label], button, input, textarea, [role="tab"]')

  for (const node of nodes) {
    const tourId = node.dataset.tourId || ''
    const label = node.getAttribute('aria-label') || node.getAttribute('title') || node.textContent?.trim() || ''

    const selector = tourId
      ? `[data-tour-id="${CSS.escape(tourId)}"]`
      : node.id
        ? `#${CSS.escape(node.id)}`
        : ''

    if (!selector || !label || seen.has(selector)) {
      continue
    }

    seen.add(selector)
    targets.push({ target: selector, label: label.slice(0, 160) })

    if (targets.length >= 100) {
      break
    }
  }

  return targets
}

export function usePreviewRouting({
  activeSessionIdRef,
  baseHandleGatewayEvent,
  currentCwd,
  currentView,
  requestGateway,
  routedSessionId,
  selectedStoredSessionId
}: PreviewRoutingOptions) {
  const previewRegistry = useStore($sessionPreviewRegistry)
  const previewSessionId = activePreviewSessionId(activeSessionIdRef, routedSessionId, selectedStoredSessionId)

  useEffect(() => {
    if (currentView !== 'chat' || !previewSessionId) {
      setPreviewTarget(null)

      return
    }

    const record = getSessionPreviewRecord(previewSessionId)

    setPreviewTarget(record?.normalized ?? null)
  }, [currentView, previewRegistry, previewSessionId])

  const registerStructuredPreview = useCallback(
    async (event: RpcEvent) => {
      if (
        event.session_id &&
        event.session_id !== activeSessionIdRef.current &&
        event.session_id !== previewSessionId
      ) {
        return
      }

      if (!event.type.startsWith('tool.')) {
        return
      }

      if (!previewSessionId) {
        return
      }

      const candidate = structuredPreviewCandidate(event.payload)

      if (!candidate) {
        return
      }

      const desktop = window.clioDesktop

      if (!desktop?.normalizePreviewTarget) {
        return
      }

      const sessionId = previewSessionId
      const cwd = currentCwd || ''
      const target = await desktop.normalizePreviewTarget(candidate, cwd || undefined).catch(() => null)

      if (
        !target ||
        sessionId !== activePreviewSessionId(activeSessionIdRef, routedSessionId, selectedStoredSessionId) ||
        $currentCwd.get() !== cwd
      ) {
        return
      }

      setSessionPreviewTarget(sessionId, target, 'tool-result', candidate)
    },
    [activeSessionIdRef, currentCwd, previewSessionId, routedSessionId, selectedStoredSessionId]
  )

  const restartPreviewServer = useCallback(
    async (url: string, context?: string) => {
      const sessionId = activeSessionIdRef.current

      if (!sessionId) {
        throw new Error('No active session for background restart')
      }

      const cwd = $currentCwd.get() || currentCwd || ''

      const result = await requestGateway<{ task_id?: string }>('preview.restart', {
        context: context || undefined,
        cwd: cwd || undefined,
        session_id: sessionId,
        url
      })

      const taskId = result.task_id || ''

      if (!taskId) {
        throw new Error('Background restart did not return a task id')
      }

      beginPreviewServerRestart(taskId, url)

      return taskId
    },
    [activeSessionIdRef, currentCwd, requestGateway]
  )

  const handleDesktopGatewayEvent = useCallback<EventHandler>(
    event => {
      baseHandleGatewayEvent(event)

      if (event.type === 'preview.restart.complete') {
        const { task_id, text } = asRecord(event.payload)

        if (typeof task_id === 'string' && task_id) {
          completePreviewServerRestart(task_id, typeof text === 'string' ? text : '')
        }
      } else if (event.type === 'preview.restart.progress') {
        const { task_id, text } = asRecord(event.payload)

        if (typeof task_id === 'string' && task_id) {
          progressPreviewServerRestart(task_id, typeof text === 'string' ? text : '')
        }
      }

      if (event.session_id && event.session_id !== activeSessionIdRef.current) {
        return
      }

      if (event.type === 'preview.open') {
        const { label, url } = asRecord(event.payload)
        const rawUrl = typeof url === 'string' ? url.trim() : ''
        const desktop = window.clioDesktop

        if (rawUrl && desktop?.normalizePreviewTarget && previewSessionId) {
          void desktop.normalizePreviewTarget(rawUrl, currentCwd || undefined)
            .then(target => {
              if (target) {
                setSessionPreviewTarget(
                  previewSessionId,
                  typeof label === 'string' && label.trim() ? { ...target, label: label.trim() } : target,
                  'tool-result',
                  rawUrl
                )
              }
            })
            .catch(() => undefined)
        }

        return
      }

      if (event.type === 'preview.close') {
        const { url } = asRecord(event.payload)
        const rawUrl = typeof url === 'string' ? url.trim() : ''

        if (!rawUrl) {
          closeRightRail()
        } else if (!closePreviewByUrl(rawUrl)) {
          void window.clioDesktop?.normalizePreviewTarget?.(rawUrl, currentCwd || undefined)
            .then(target => {
              if (target) {
                closePreviewByUrl(target.url)
              }
            })
            .catch(() => undefined)
        }

        return
      }

      if (event.type === 'desktop_ui.request') {
        const request = asRecord(event.payload)
        const requestId = typeof request.request_id === 'string' ? request.request_id : ''
        const action = typeof request.action === 'string' ? request.action : ''
        const args = asRecord(request.payload)

        void (async () => {
          let result: unknown

          if (action === 'preview.read') {
            result = desktopUiPreviewSnapshot(Number(args.start || 0), Number(args.count || 12_000))
          } else if (action === 'preview.drive') {
            result = await driveActivePreview(args)
          } else if (action === 'preview.annotate') {
            result = await annotateActivePreview(args)
          } else if (action === 'tour.targets') {
            result = { targets: desktopUiTourTargets() }
          } else if (action === 'terminal.read') {
            result = readDesktopTerminal(Number(args.start || 0), Number(args.count || 12_000))
          } else if (action === 'window.read_below') {
            result = { error: 'Window-below metadata is unavailable on this desktop backend' }
          } else {
            result = { error: `Unsupported desktop UI request: ${action || '(empty)'}` }
          }

          if (requestId) {
            await requestGateway('desktop_ui.respond', {
              request_id: requestId,
              result: JSON.stringify(result)
            }).catch(() => undefined)
          }
        })()

        return
      }

      if (handleDesktopUiAction(event.type, asRecord(event.payload))) {
        return
      }

      void registerStructuredPreview(event)

      if ($previewTarget.get()?.kind === 'url' && gatewayEventCompletedFileDiff(event)) {
        requestPreviewReload()
      }
    },
    [
      activeSessionIdRef,
      baseHandleGatewayEvent,
      currentCwd,
      previewSessionId,
      registerStructuredPreview,
      requestGateway
    ]
  )

  return { handleDesktopGatewayEvent, restartPreviewServer }
}
