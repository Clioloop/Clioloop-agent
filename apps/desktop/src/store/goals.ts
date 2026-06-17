import { atom } from 'nanostores'

/**
 * Standing-goal state, surfaced as a banner so a session running a ``/goal``
 * loop is visually distinct from a normal task — the same distinction the TUI
 * and Telegram already show. Fed by ``status.update`` events of
 * ``kind: 'goal'`` emitted by the gateway (see tui_gateway ``_emit_goal_event``).
 */

export type GoalStatus = 'active' | 'cleared' | 'done' | 'paused'

export interface GoalState {
  goal: string
  /** active|paused keep the banner up; done shows the ✓ result until dismissed. */
  status: GoalStatus
  turnsUsed: number
  maxTurns: number
  subgoals: number
  reason?: string
  verdict?: string
  /** The human one-liner the gateway sent (e.g. "↻ Continuing toward goal (3/20)…"). */
  lastText?: string
  updatedAt: number
}

/** sessionId -> active/visible goal. Sessions without a goal are absent. */
export const $goalsBySession = atom<Record<string, GoalState>>({})

export interface GoalEventPayload {
  active?: boolean
  goal?: string
  kind?: string
  max_turns?: null | number
  reason?: null | string
  status?: string
  subgoals?: null | number
  text?: string
  turns_used?: null | number
  verdict?: null | string
}

function normalizeStatus(raw: unknown): GoalStatus {
  const s = typeof raw === 'string' ? raw.toLowerCase() : ''

  if (s === 'paused' || s === 'done' || s === 'cleared') {return s}

  return 'active'
}

function setEntry(sessionId: string, next: GoalState | null): void {
  const current = $goalsBySession.get()

  if (next === null) {
    if (!(sessionId in current)) {return}
    const { [sessionId]: _drop, ...rest } = current
    $goalsBySession.set(rest)

    return
  }

  $goalsBySession.set({ ...current, [sessionId]: next })
}

/**
 * Apply a ``kind: 'goal'`` status event. ``cleared`` (and a bare
 * ``active: false`` that isn't a paused/done state) retires the banner;
 * everything else upserts the current goal so the banner reflects live
 * progress.
 */
export function applyGoalEvent(sessionId: string, payload: GoalEventPayload): void {
  if (!sessionId || payload?.kind !== 'goal') {return}

  const status = normalizeStatus(payload.status)

  if (status === 'cleared') {
    setEntry(sessionId, null)

    return
  }

  const prev = $goalsBySession.get()[sessionId]
  const goal = (payload.goal ?? prev?.goal ?? '').trim()

  // A goal event with no text and no goal we can recover is not renderable.
  if (!goal && !payload.text) {return}

  setEntry(sessionId, {
    goal: goal || prev?.goal || '',
    lastText: payload.text || prev?.lastText,
    maxTurns: numberOr(payload.max_turns, prev?.maxTurns ?? 0),
    reason: payload.reason ?? prev?.reason ?? undefined,
    status,
    subgoals: numberOr(payload.subgoals, prev?.subgoals ?? 0),
    turnsUsed: numberOr(payload.turns_used, prev?.turnsUsed ?? 0),
    updatedAt: Date.now(),
    verdict: payload.verdict ?? prev?.verdict ?? undefined
  })
}

function numberOr(value: null | number | undefined, fallback: number): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

/** User dismissed the banner (e.g. after a done/paused goal). */
export function dismissGoal(sessionId: string): void {
  setEntry(sessionId, null)
}

/** Drop a session's goal from the map (session reset/delete). */
export function clearGoalForSession(sessionId: string): void {
  setEntry(sessionId, null)
}
