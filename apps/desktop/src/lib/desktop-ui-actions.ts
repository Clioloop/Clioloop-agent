import { FILE_BROWSER_PANE_ID, setSidebarOpen } from '@/store/layout'
import { setPaneOpen } from '@/store/panes'

export type DesktopUiAction =
  | 'layout.apply'
  | 'message.react'
  | 'pane.focus'
  | 'terminal.close'
  | 'tour.control'

function asString(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

export function applyDesktopLayout(preset: string): void {
  const name = preset.trim().toLowerCase()

  setSidebarOpen(name !== 'focus')
  setPaneOpen(FILE_BROWSER_PANE_ID, name === 'coding' || name === 'review')
  setPaneOpen('terminal', name === 'coding')
  setPaneOpen('git-review', name === 'review')
}

export function focusDesktopPane(pane: string): boolean {
  const name = pane.trim().toLowerCase()

  if (name === 'sessions') {
    setSidebarOpen(true)
  } else if (name === 'files') {
    setPaneOpen(FILE_BROWSER_PANE_ID, true)
  } else if (name === 'terminal') {
    setPaneOpen('terminal', true)
  } else if (name === 'review') {
    setPaneOpen('git-review', true)
  } else if (name !== 'chat' && name !== 'preview') {
    return false
  }

  queueMicrotask(() => {
    const selector = name === 'sessions'
      ? '[data-pane-id="chat-sidebar"]'
      : name === 'files'
        ? '[data-pane-id="file-browser"]'
        : name === 'preview'
          ? '[data-pane-id="preview"]'
          : name === 'review'
            ? '[data-pane-id="git-review"]'
            : name === 'terminal'
              ? '[data-pane-id="terminal"]'
              : '[data-pane-id="chat"], main'

    document.querySelector<HTMLElement>(selector)?.focus({ preventScroll: true })
  })

  return true
}

const TOUR_ROOT_ID = 'clio-guided-tour-overlay'

function removeTour(): void {
  document.getElementById(TOUR_ROOT_ID)?.remove()
}

function showTourStep(step: Record<string, unknown>, index: number, steps: Record<string, unknown>[]): void {
  removeTour()
  const selector = asString(step.target)
  const target = selector ? document.querySelector<HTMLElement>(selector) : null

  if (!target) {
    return
  }

  const root = document.createElement('div')
  root.id = TOUR_ROOT_ID
  root.style.position = 'fixed'
  root.style.inset = '0'
  root.style.zIndex = '2147483000'
  root.style.pointerEvents = 'none'

  const box = target.getBoundingClientRect()
  const ring = document.createElement('div')
  ring.style.position = 'fixed'
  ring.style.left = `${Math.max(0, box.left - 6)}px`
  ring.style.top = `${Math.max(0, box.top - 6)}px`
  ring.style.width = `${Math.max(1, box.width + 12)}px`
  ring.style.height = `${Math.max(1, box.height + 12)}px`
  ring.style.border = '2px solid var(--ui-accent, #7c9cff)'
  ring.style.borderRadius = '10px'
  ring.style.boxShadow = '0 0 0 9999px rgb(0 0 0 / 55%)'

  const card = document.createElement('section')
  card.style.position = 'fixed'
  card.style.pointerEvents = 'auto'
  card.style.left = `${Math.max(12, Math.min(window.innerWidth - 332, box.left))}px`
  card.style.top = `${Math.min(window.innerHeight - 190, Math.max(12, box.bottom + 14))}px`
  card.style.width = '320px'
  card.style.padding = '14px'
  card.style.borderRadius = '12px'
  card.style.background = 'var(--ui-editor-surface-background, #17191d)'
  card.style.color = 'var(--ui-text-primary, white)'
  card.style.boxShadow = '0 18px 60px rgb(0 0 0 / 45%)'

  const title = document.createElement('strong')
  title.textContent = asString(step.title) || `Step ${index + 1}`
  const body = document.createElement('p')
  body.textContent = asString(step.text)
  body.style.margin = '8px 0 12px'

  const controls = document.createElement('div')
  controls.style.display = 'flex'
  controls.style.gap = '8px'
  controls.style.justifyContent = 'flex-end'

  const close = document.createElement('button')
  close.textContent = 'Close'
  close.onclick = removeTour
  controls.append(close)

  if (index > 0) {
    const previous = document.createElement('button')
    previous.textContent = 'Previous'
    previous.onclick = () => showTourStep(steps[index - 1] ?? {}, index - 1, steps)
    controls.append(previous)
  }

  if (index + 1 < steps.length) {
    const next = document.createElement('button')
    next.textContent = 'Next'
    next.onclick = () => showTourStep(steps[index + 1] ?? {}, index + 1, steps)
    controls.append(next)
  }

  card.append(title, body, controls)
  root.append(ring, card)
  document.body.append(root)
  target.scrollIntoView({ block: 'nearest', inline: 'nearest' })
}

export function controlDesktopTour(payload: Record<string, unknown>): boolean {
  const action = asString(payload.action).toLowerCase()

  if (action === 'stop') {
    removeTour()

    return true
  }

  const steps = Array.isArray(payload.steps)
    ? payload.steps.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === 'object'))
    : []

  if ((action === 'show' || action === 'start') && steps.length) {
    showTourStep(steps[0] ?? {}, 0, steps)

    return true
  }

  return false
}

export function handleDesktopUiAction(action: string, payload: Record<string, unknown>): boolean {
  if (action === 'pane.focus') {
    return focusDesktopPane(asString(payload.pane))
  }

  if (action === 'layout.apply') {
    applyDesktopLayout(asString(payload.preset) || 'default')

    return true
  }

  if (action === 'tour.control') {
    return controlDesktopTour(payload)
  }

  if (action === 'terminal.close') {
    setPaneOpen('terminal', false)

    return true
  }

  if (action === 'message.react') {
    window.dispatchEvent(new CustomEvent('clio:message-react', { detail: payload }))

    return true
  }

  return false
}
