import { useStore } from '@nanostores/react'

import { Codicon } from '@/components/ui/codicon'
import { cn } from '@/lib/utils'
import { $goalsBySession, dismissGoal, type GoalState, type GoalStatus } from '@/store/goals'

interface GoalBannerProps {
  sessionId: null | string
}

interface StatusStyle {
  accent: string
  glyph: string
  label: string
  spin?: boolean
  track: string
}

const STATUS_STYLES: Record<GoalStatus, StatusStyle> = {
  active: { accent: 'text-sky-500', glyph: 'target', label: 'Goal', spin: false, track: 'bg-sky-500' },
  cleared: { accent: 'text-(--ui-text-tertiary)', glyph: 'circle-slash', label: 'Goal', track: 'bg-(--ui-text-tertiary)' },
  done: { accent: 'text-emerald-500', glyph: 'pass-filled', label: 'Goal achieved', track: 'bg-emerald-500' },
  paused: { accent: 'text-amber-500', glyph: 'debug-pause', label: 'Goal paused', track: 'bg-amber-500' }
}

function progressPercent(goal: GoalState): number {
  if (!goal.maxTurns || goal.maxTurns <= 0) {return 0}

  return Math.min(100, Math.round((goal.turnsUsed / goal.maxTurns) * 100))
}

/**
 * A banner that makes a session running a ``/goal`` loop visually distinct
 * from a normal task — the same distinction the TUI and Telegram show. Renders
 * nothing when the active session has no goal. Fed by {@link $goalsBySession}.
 */
export function GoalBanner({ sessionId }: GoalBannerProps) {
  const goals = useStore($goalsBySession)
  const goal = sessionId ? goals[sessionId] : undefined

  if (!sessionId || !goal) {return null}

  const style = STATUS_STYLES[goal.status] ?? STATUS_STYLES.active
  const isLooping = goal.status === 'active'
  const pct = progressPercent(goal)
  const subline = goal.lastText || goal.reason || ''

  return (
    <div className="shrink-0 px-3 pt-2">
    <div
      className={cn(
        'pointer-events-auto mx-auto w-full max-w-[var(--chat-max-width,48rem)]',
        'rounded-lg border border-(--ui-stroke-tertiary) bg-(--ui-chat-surface-background)',
        'px-3 py-2 text-[0.8125rem] shadow-sm'
      )}
      data-goal-status={goal.status}
      data-testid="goal-banner"
    >
      <div className="flex items-center gap-2">
        <Codicon
          className={cn('shrink-0', style.accent)}
          name={isLooping ? 'sync' : style.glyph}
          size="0.9375rem"
          spinning={isLooping}
        />
        <span className={cn('shrink-0 text-[0.6875rem] font-semibold uppercase tracking-wide', style.accent)}>
          {style.label}
        </span>
        <span className="min-w-0 flex-1 truncate font-medium text-foreground" title={goal.goal}>
          {goal.goal}
        </span>
        {goal.subgoals > 0 && (
          <span className="shrink-0 rounded-full bg-(--ui-bg-tertiary) px-1.5 py-0.5 text-[0.6875rem] text-(--ui-text-secondary)">
            +{goal.subgoals} subgoal{goal.subgoals === 1 ? '' : 's'}
          </span>
        )}
        {goal.maxTurns > 0 && (
          <span className="shrink-0 tabular-nums text-[0.6875rem] text-(--ui-text-tertiary)">
            {goal.turnsUsed}/{goal.maxTurns} turns
          </span>
        )}
        <button
          aria-label="Dismiss goal"
          className="shrink-0 rounded p-0.5 text-(--ui-text-tertiary) hover:bg-(--ui-control-hover-background) hover:text-foreground"
          onClick={() => dismissGoal(sessionId)}
          type="button"
        >
          <Codicon name="close" size="0.8125rem" />
        </button>
      </div>

      {goal.maxTurns > 0 && (
        <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-(--ui-bg-tertiary)">
          <div className={cn('h-full rounded-full transition-all', style.track)} style={{ width: `${pct}%` }} />
        </div>
      )}

      {subline && (
        <p className="mt-1 truncate text-[0.75rem] text-(--ui-text-tertiary)" title={subline}>
          {subline}
        </p>
      )}
    </div>
    </div>
  )
}
