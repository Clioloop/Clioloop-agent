import type { PreviewActHolder } from './act-in-page'

export interface PreviewAnnotationAction {
  kind: 'add' | 'clear' | 'hold' | 'remove'
  label?: string
  ref?: string
  selector?: string
}

export interface PreviewAnnotationResult {
  acted?: string
  count?: number
  error?: string
  success: boolean
  title?: string
  url?: string
}

interface PreviewAnnotationItem {
  el: Element
  key: string
  label: string
  mark: HTMLElement
}

interface PreviewAnnotationState {
  cleanup: () => void
  items: Record<string, PreviewAnnotationItem>
  layer: HTMLElement
  mutation?: MutationObserver
  refresh: () => void
  resize?: ResizeObserver
}

export interface PreviewAnnotationHolder extends PreviewActHolder {
  annotationState?: PreviewAnnotationState
}

/**
 * Manage persistent, element-bound marks inside one preview document.
 *
 * The pane injects this function with `toString()`, so its body deliberately
 * has no module-scope dependencies. State lives on the same per-document holder
 * as inventory refs. A navigation destroys that holder; a session-scope change
 * calls its cleanup before installing a fresh one.
 */
export function annotateInPage(
  doc: Document,
  holder: PreviewAnnotationHolder,
  action: PreviewAnnotationAction
): PreviewAnnotationResult {
  const win = doc.defaultView
  const here = doc.location?.href || ''

  const answer = (result: PreviewAnnotationResult): PreviewAnnotationResult => ({
    ...result,
    title: doc.title || '',
    url: here
  })

  const fail = (error: string) => answer({ error, success: false })

  const clearState = (state: PreviewAnnotationState) => {
    for (const item of Object.values(state.items)) {
      item.mark.remove()
    }

    state.items = {}
  }

  const buildState = (): PreviewAnnotationState => {
    const layer = doc.createElement('div')

    layer.dataset.clioPreviewAnnotations = 'true'
    Object.assign(layer.style, {
      inset: '0',
      overflow: 'hidden',
      pointerEvents: 'none',
      position: 'fixed',
      zIndex: '2147483646'
    })
    doc.documentElement.append(layer)

    const state = {
      cleanup: () => undefined,
      items: {},
      layer,
      refresh: () => undefined
    } as PreviewAnnotationState

    state.refresh = () => {
      for (const [key, item] of Object.entries(state.items)) {
        if (!doc.contains(item.el)) {
          item.mark.remove()
          delete state.items[key]

          continue
        }

        const box = item.el.getBoundingClientRect()
        const visible = box.width >= 1 && box.height >= 1 && box.right > 0 && box.bottom > 0

        item.mark.style.display = visible ? 'block' : 'none'

        if (!visible) {
          continue
        }

        Object.assign(item.mark.style, {
          height: `${Math.max(0, box.height)}px`,
          left: `${box.left}px`,
          top: `${box.top}px`,
          width: `${Math.max(0, box.width)}px`
        })
      }
    }

    const onMove = () => state.refresh()

    win?.addEventListener('resize', onMove)
    win?.addEventListener('scroll', onMove, true)

    if (typeof MutationObserver === 'function' && doc.body) {
      state.mutation = new MutationObserver(onMove)
      state.mutation.observe(doc.body, { childList: true, subtree: true })
    }

    if (typeof ResizeObserver === 'function') {
      state.resize = new ResizeObserver(onMove)
    }

    state.cleanup = () => {
      clearState(state)
      state.mutation?.disconnect()
      state.resize?.disconnect()
      win?.removeEventListener('resize', onMove)
      win?.removeEventListener('scroll', onMove, true)
      layer.remove()
    }

    return state
  }

  const state = holder.annotationState || (holder.annotationState = buildState())

  const resolve = (): { el?: Element; error?: string; key?: string } => {
    const ref = (action.ref || '').trim()

    if (ref) {
      if (holder.url !== here) {
        return { error: `The page navigated, so ${ref} is stale. Run drive_preview inventory again.` }
      }

      const bound = (holder.book || []).find(entry => entry.ref === ref)

      if (!bound || !doc.contains(bound.el)) {
        return { error: `Unknown or removed preview ref ${ref}. Run drive_preview inventory again.` }
      }

      return { el: bound.el, key: `ref:${ref}` }
    }

    const selector = (action.selector || '').trim()

    if (!selector) {
      return { error: 'Pass a ref from drive_preview inventory or a CSS selector.' }
    }

    try {
      const el = doc.querySelector(selector)

      return el ? { el, key: `selector:${selector}` } : { error: `No element matches ${selector}.` }
    } catch {
      return { error: `Not a valid CSS selector: ${selector}` }
    }
  }

  const nameOf = (el: Element, fallback: string): string => {
    const bound = (holder.book || []).find(entry => entry.el === el)

    return (
      fallback ||
      bound?.label ||
      el.getAttribute('aria-label') ||
      el.textContent?.trim().replace(/\s+/g, ' ').slice(0, 80) ||
      el.tagName.toLowerCase()
    )
  }

  const add = (key: string, el: Element, label: string) => {
    state.items[key]?.mark.remove()

    const mark = doc.createElement('div')
    const caption = doc.createElement('span')

    Object.assign(mark.style, {
      border: '2px solid #8b5cf6',
      borderRadius: '6px',
      boxShadow: '0 0 0 2px rgba(139, 92, 246, 0.22)',
      boxSizing: 'border-box',
      pointerEvents: 'none',
      position: 'fixed'
    })
    Object.assign(caption.style, {
      background: '#7c3aed',
      borderRadius: '4px 4px 4px 0',
      color: '#fff',
      font: '600 11px/1.4 system-ui, sans-serif',
      left: '-2px',
      maxWidth: '240px',
      overflow: 'hidden',
      padding: '2px 6px',
      position: 'absolute',
      textOverflow: 'ellipsis',
      top: '-22px',
      whiteSpace: 'nowrap'
    })
    caption.textContent = label
    caption.hidden = !label
    mark.append(caption)
    state.layer.append(mark)
    state.items[key] = { el, key, label, mark }
    state.resize?.observe(el)
    state.refresh()
  }

  if (action.kind === 'clear') {
    clearState(state)

    return answer({ acted: 'cleared preview annotations', count: 0, success: true })
  }

  if (action.kind === 'hold') {
    clearState(state)

    for (const [index, el] of (holder.field || []).entries()) {
      const bound = (holder.book || []).find(entry => entry.el === el)
      const key = bound?.ref ? `ref:${bound.ref}` : `hold:${index}`

      add(key, el, nameOf(el, bound?.label || ''))
    }

    const count = Object.keys(state.items).length

    return answer({ acted: 'held the visible interactive field', count, success: true })
  }

  const target = resolve()

  if (target.error || !target.el || !target.key) {
    return fail(target.error || 'No annotation target.')
  }

  if (action.kind === 'remove') {
    const item = state.items[target.key]

    item?.mark.remove()
    delete state.items[target.key]

    return answer({ acted: `removed annotation from ${nameOf(target.el, '')}`, count: Object.keys(state.items).length, success: true })
  }

  const label = nameOf(target.el, (action.label || '').trim().slice(0, 80))

  add(target.key, target.el, label)

  return answer({ acted: `annotated ${nameOf(target.el, '')}`, count: Object.keys(state.items).length, success: true })
}
