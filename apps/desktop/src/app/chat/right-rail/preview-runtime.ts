import {
  actInPage,
  type PreviewActAction,
  type PreviewActResult
} from '@/lib/preview-act/act-in-page'
import {
  annotateInPage,
  type PreviewAnnotationAction,
  type PreviewAnnotationResult
} from '@/lib/preview-act/annotate-in-page'
import { $rightRailActiveTabId } from '@/store/layout'
import { $activeSessionId, $selectedStoredSessionId } from '@/store/session'

import { clickAt, glideTo, pointerPlaced, pressKey, selectAll, typeText, wheelBy } from './preview-drive'

export type PreviewInputEvent =
  | { button: 'left'; clickCount: number; type: 'mouseDown' | 'mouseUp'; x: number; y: number }
  | { deltaX: number; deltaY: number; type: 'mouseWheel'; x: number; y: number }
  | { keyCode: string; modifiers?: string[]; type: 'char' | 'keyDown' | 'keyUp' }
  | { type: 'mouseMove'; x: number; y: number }

export interface PreviewRuntime {
  back: () => Promise<void> | void
  focus: () => void
  forward: () => Promise<void> | void
  reload: () => Promise<void> | void
  run: (code: string) => Promise<unknown>
  send: (event: PreviewInputEvent) => Promise<void>
}

export interface ActivePreviewRuntime extends PreviewRuntime {
  key: string
}

export interface PreviewDriveRequest {
  action?: unknown
  amount?: unknown
  full?: unknown
  key?: unknown
  max?: unknown
  ref?: unknown
  selector?: unknown
  submit?: unknown
  text?: unknown
  to?: unknown
}

export interface PreviewAnnotateRequest {
  action?: unknown
  label?: unknown
  ref?: unknown
  selector?: unknown
}

const runtimes = new Map<string, PreviewRuntime>()
const STROBE_PASSES = 3
const STROBE_MAX_ELEMENTS = 32

export function previewRuntimeKey(sessionId: string, tabId: string): string {
  return `${sessionId.trim()}\u0000${tabId}`
}

export function registerPreviewRuntime(key: string, runtime: PreviewRuntime): () => void {
  runtimes.set(key, runtime)

  return () => {
    if (runtimes.get(key) === runtime) {
      runtimes.delete(key)
    }
  }
}

export function activePreviewRuntime(): ActivePreviewRuntime | null {
  const sessionId = $selectedStoredSessionId.get() || $activeSessionId.get() || ''
  const tabId = $rightRailActiveTabId.get()

  if (!sessionId || !tabId) {
    return null
  }

  const key = previewRuntimeKey(sessionId, tabId)
  const runtime = runtimes.get(key)

  return runtime ? { ...runtime, key } : null
}

const holderName = '__clioPreviewActState'

function injectedCall(fn: { toString: () => string }, action: object): string {
  return `(() => {
    const key = ${JSON.stringify(holderName)};
    let holder = window[key] || (window[key] = {});
    const here = document.location ? document.location.href : '';
    if (holder.url && holder.url !== here) {
      if (holder.annotationState && typeof holder.annotationState.cleanup === 'function') {
        holder.annotationState.cleanup();
      }
      holder = window[key] = {};
    }
    return (${fn.toString()})(document, holder, ${JSON.stringify(action)});
  })()`
}

function record(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : null
}

async function runAct(runtime: PreviewRuntime, action: PreviewActAction): Promise<PreviewActResult> {
  const result = record(await runtime.run(injectedCall(actInPage, action)))

  if (!result || typeof result.success !== 'boolean') {
    throw new Error('The active preview returned an invalid action result')
  }

  return result as unknown as PreviewActResult
}

async function afterTrustedAction(
  runtime: PreviewRuntime,
  receipt: PreviewActResult,
  acted: string
): Promise<PreviewActResult> {
  try {
    const snapshot = await runAct(runtime, { kind: 'elements' })

    return { ...snapshot, acted, success: true }
  } catch (error) {
    return {
      ...receipt,
      acted,
      note: `The trusted action completed, but the updated inventory is not ready: ${
        error instanceof Error ? error.message : String(error)
      }`,
      success: true
    }
  }
}

function unavailable(): PreviewActResult {
  return {
    error: 'No active web preview can receive trusted input. Open a web preview and select its tab first.',
    success: false
  }
}

/** Drive only the currently selected preview runtime. Synthetic page events are
 * never used as a fallback: missing Electron input fails the action explicitly. */
export async function driveActivePreview(request: PreviewDriveRequest): Promise<PreviewActResult> {
  const runtime = activePreviewRuntime()

  if (!runtime) {
    return unavailable()
  }

  const action = typeof request.action === 'string' ? request.action : ''
  const ref = typeof request.ref === 'string' ? request.ref : undefined
  const selector = typeof request.selector === 'string' ? request.selector : undefined

  try {
    if (action === 'inventory') {
      return await runAct(runtime, {
        full: request.full === true,
        kind: 'elements',
        max: typeof request.max === 'number' ? request.max : undefined
      })
    }

    if (action === 'back' || action === 'forward' || action === 'reload') {
      await runtime[action]()

      return {
        acted: action === 'reload' ? 'reloaded the preview' : `navigated ${action}`,
        note: 'Page is loading — run inventory to see the current page.',
        success: true
      }
    }

    if (action === 'strobe') {
      const requestedMax = typeof request.max === 'number' && Number.isFinite(request.max) ? request.max : STROBE_MAX_ELEMENTS
      const max = Math.max(1, Math.min(Math.floor(requestedMax), STROBE_MAX_ELEMENTS))
      let snapshot: PreviewActResult = { success: true }

      // This deliberately samples rather than flashes: source parity keeps the
      // strobe verb, but Clio does not install a page overlay or mutate a visual
      // theme. Both pass count and inventory size are fixed safety bounds.
      for (let pass = 0; pass < STROBE_PASSES; pass++) {
        snapshot = await runAct(runtime, { kind: 'elements', max })

        if (!snapshot.success) {
          return snapshot
        }
      }

      return {
        ...snapshot,
        acted: `strobed the preview with ${STROBE_PASSES} bounded read-only scans`,
        note: 'No input was sent and no page or desktop theme was changed.',
        success: true
      }
    }

    if (action === 'scroll') {
      runtime.focus()

      if (ref || selector) {
        const located = await runAct(runtime, { focus: true, kind: 'locate', ref, selector })

        if (!located.success || !located.point) {
          return located
        }

        await glideTo(runtime, located.point)
      } else if (!pointerPlaced()) {
        const centre = record(
          await runtime.run('({ x: Math.round(window.innerWidth / 2), y: Math.round(window.innerHeight / 2) })')
        )

        if (!centre || typeof centre.x !== 'number' || typeof centre.y !== 'number') {
          throw new Error('Could not locate the active preview viewport for trusted scrolling')
        }

        await glideTo(runtime, { x: centre.x, y: centre.y })
      }

      if (request.to === 'top' || request.to === 'bottom') {
        await pressKey(runtime, request.to === 'top' ? 'Home' : 'End')
      } else {
        const amount =
          typeof request.amount === 'number'
            ? request.amount
            : Number(await runtime.run('Math.round(window.innerHeight * 0.9)'))

        if (!Number.isFinite(amount)) {
          throw new Error('Could not determine a trusted preview scroll distance')
        }

        await wheelBy(runtime, amount)
      }

      return await afterTrustedAction(runtime, { success: true }, 'scrolled the preview')
    }

    if (!['click', 'hover', 'press', 'type'].includes(action)) {
      return { error: `Unsupported preview drive action: ${action || '(empty)'}`, success: false }
    }

    const located = await runAct(runtime, {
      focus: action === 'press' || action === 'type',
      kind: 'locate',
      ref,
      selector
    })

    if (!located.success || !located.point) {
      return located
    }

    runtime.focus()
    await glideTo(runtime, located.point)

    const target = located.acted?.replace(/^looking at /, '') || 'the target'
    let acted = ''

    if (action === 'click') {
      await clickAt(runtime)
      acted = `clicked ${target}`
    } else if (action === 'hover') {
      acted = `hovered over ${target}`
    } else if (action === 'type') {
      if (!located.typable) {
        return { ...located, error: `${target} is not a text field.`, success: false }
      }

      await selectAll(runtime)
      await typeText(runtime, typeof request.text === 'string' ? request.text : '')

      if (request.submit === true) {
        await pressKey(runtime, 'Enter')
      }

      acted = `typed into ${target}${request.submit === true ? ' and submitted' : ''}`
    } else {
      const key = typeof request.key === 'string' ? request.key.trim() : ''

      if (!key) {
        return { ...located, error: 'Pass the key to press.', success: false }
      }

      await pressKey(runtime, key)
      acted = `pressed ${key} on ${target}`
    }

    return await afterTrustedAction(runtime, located, acted)
  } catch (error) {
    return {
      error: `Trusted preview input failed: ${error instanceof Error ? error.message : String(error)}`,
      success: false
    }
  }
}

export async function annotateActivePreview(request: PreviewAnnotateRequest): Promise<PreviewAnnotationResult> {
  const runtime = activePreviewRuntime()

  if (!runtime) {
    return { error: 'No active web preview is available to annotate. Select a web preview tab first.', success: false }
  }

  const action: PreviewAnnotationAction = {
    kind:
      request.action === 'clear' || request.action === 'hold' || request.action === 'remove'
        ? request.action
        : 'add',
    label: typeof request.label === 'string' ? request.label : undefined,
    ref: typeof request.ref === 'string' ? request.ref : undefined,
    selector: typeof request.selector === 'string' ? request.selector : undefined
  }

  try {
    const result = record(await runtime.run(injectedCall(annotateInPage, action)))

    if (!result || typeof result.success !== 'boolean') {
      throw new Error('The active preview returned an invalid annotation result')
    }

    return result as unknown as PreviewAnnotationResult
  } catch (error) {
    return {
      error: `Could not annotate the active preview: ${error instanceof Error ? error.message : String(error)}`,
      success: false
    }
  }
}
