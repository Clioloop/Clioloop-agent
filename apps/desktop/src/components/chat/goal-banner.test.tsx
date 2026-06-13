// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { $goalsBySession, applyGoalEvent } from '@/store/goals'

import { GoalBanner } from './goal-banner'

const SID = 'sess-1'

describe('GoalBanner', () => {
  beforeEach(() => {
    $goalsBySession.set({})
  })

  afterEach(() => {
    cleanup()
  })

  it('renders nothing when the session has no goal', () => {
    render(<GoalBanner sessionId={SID} />)
    expect(screen.queryByTestId('goal-banner')).toBeNull()
  })

  it('renders nothing when sessionId is null', () => {
    applyGoalEvent(SID, { goal: 'X', kind: 'goal', max_turns: 20, status: 'active', turns_used: 0 })
    render(<GoalBanner sessionId={null} />)
    expect(screen.queryByTestId('goal-banner')).toBeNull()
  })

  it('shows an active goal with progress and goal text', () => {
    applyGoalEvent(SID, {
      goal: 'Refactor the auth module',
      kind: 'goal',
      max_turns: 20,
      status: 'active',
      text: '↻ Continuing toward goal (3/20)',
      turns_used: 3
    })
    render(<GoalBanner sessionId={SID} />)
    const banner = screen.getByTestId('goal-banner')
    expect(banner.getAttribute('data-goal-status')).toBe('active')
    expect(banner.textContent).toContain('Refactor the auth module')
    expect(banner.textContent).toContain('3/20 turns')
    expect(banner.textContent).toContain('Continuing toward goal')
  })

  it('shows a done goal distinctly', () => {
    applyGoalEvent(SID, { goal: 'Done thing', kind: 'goal', max_turns: 20, status: 'done', text: '✓ Goal achieved', turns_used: 5 })
    render(<GoalBanner sessionId={SID} />)
    const banner = screen.getByTestId('goal-banner')
    expect(banner.getAttribute('data-goal-status')).toBe('done')
    expect(banner.textContent).toContain('Goal achieved')
  })

  it('shows subgoal count when present', () => {
    applyGoalEvent(SID, {
      goal: 'Multi-criteria goal',
      kind: 'goal',
      max_turns: 20,
      status: 'active',
      subgoals: 2,
      turns_used: 1
    })
    render(<GoalBanner sessionId={SID} />)
    expect(screen.getByTestId('goal-banner').textContent).toContain('+2 subgoals')
  })

  it('dismiss button retires the banner', () => {
    applyGoalEvent(SID, { goal: 'Dismiss me', kind: 'goal', max_turns: 20, status: 'paused', turns_used: 1 })
    render(<GoalBanner sessionId={SID} />)
    expect(screen.getByTestId('goal-banner')).toBeTruthy()
    fireEvent.click(screen.getByLabelText('Dismiss goal'))
    expect($goalsBySession.get()[SID]).toBeUndefined()
  })
})
