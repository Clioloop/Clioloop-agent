import { beforeEach, describe, expect, it } from 'vitest'

import {
  $goalsBySession,
  applyGoalEvent,
  clearGoalForSession,
  dismissGoal,
  type GoalEventPayload
} from './goals'

const SID = 'sess-1'

function goalEvent(overrides: Partial<GoalEventPayload> = {}): GoalEventPayload {
  return {
    active: true,
    goal: 'Ship the release',
    kind: 'goal',
    max_turns: 20,
    status: 'active',
    turns_used: 0,
    ...overrides
  }
}

describe('goals store', () => {
  beforeEach(() => {
    $goalsBySession.set({})
  })

  it('ignores non-goal status events', () => {
    applyGoalEvent(SID, { kind: 'status', text: 'thinking' })
    expect($goalsBySession.get()[SID]).toBeUndefined()
  })

  it('ignores events with no session id', () => {
    applyGoalEvent('', goalEvent())
    expect(Object.keys($goalsBySession.get())).toHaveLength(0)
  })

  it('creates a goal entry on set', () => {
    applyGoalEvent(SID, goalEvent({ text: '⊙ Goal set: Ship the release' }))
    const entry = $goalsBySession.get()[SID]
    expect(entry).toBeDefined()
    expect(entry.goal).toBe('Ship the release')
    expect(entry.status).toBe('active')
    expect(entry.maxTurns).toBe(20)
    expect(entry.turnsUsed).toBe(0)
  })

  it('updates progress across turns, preserving the goal text', () => {
    applyGoalEvent(SID, goalEvent())
    applyGoalEvent(SID, {
      kind: 'goal',
      reason: 'still working',
      status: 'active',
      text: '↻ Continuing toward goal (3/20)',
      turns_used: 3
      // note: no `goal` field — must be preserved from the prior event
    })
    const entry = $goalsBySession.get()[SID]
    expect(entry.goal).toBe('Ship the release')
    expect(entry.turnsUsed).toBe(3)
    expect(entry.lastText).toContain('Continuing')
    expect(entry.reason).toBe('still working')
  })

  it('marks the goal done but keeps the banner until dismissed', () => {
    applyGoalEvent(SID, goalEvent())
    applyGoalEvent(SID, { kind: 'goal', status: 'done', text: '✓ Goal achieved', turns_used: 5 })
    expect($goalsBySession.get()[SID].status).toBe('done')
  })

  it('reflects a paused goal', () => {
    applyGoalEvent(SID, goalEvent())
    applyGoalEvent(SID, { active: false, kind: 'goal', status: 'paused', text: '⏸ Goal paused' })
    expect($goalsBySession.get()[SID].status).toBe('paused')
  })

  it('retires the banner on a cleared event', () => {
    applyGoalEvent(SID, goalEvent())
    applyGoalEvent(SID, { active: false, kind: 'goal', status: 'cleared', text: '✓ Goal cleared.' })
    expect($goalsBySession.get()[SID]).toBeUndefined()
  })

  it('keeps goals isolated per session', () => {
    applyGoalEvent('a', goalEvent({ goal: 'Goal A' }))
    applyGoalEvent('b', goalEvent({ goal: 'Goal B' }))
    expect($goalsBySession.get().a.goal).toBe('Goal A')
    expect($goalsBySession.get().b.goal).toBe('Goal B')
    dismissGoal('a')
    expect($goalsBySession.get().a).toBeUndefined()
    expect($goalsBySession.get().b.goal).toBe('Goal B')
  })

  it('dismiss and clear remove the entry', () => {
    applyGoalEvent(SID, goalEvent())
    dismissGoal(SID)
    expect($goalsBySession.get()[SID]).toBeUndefined()
    applyGoalEvent(SID, goalEvent())
    clearGoalForSession(SID)
    expect($goalsBySession.get()[SID]).toBeUndefined()
  })
})
