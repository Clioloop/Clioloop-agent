import { useCallback, useEffect, useRef, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Codicon } from '@/components/ui/codicon'
import { Input } from '@/components/ui/input'
import {
  createKanbanTask,
  getKanbanBoard,
  type KanbanBoard,
  type KanbanColumn,
  type KanbanTask,
  updateKanbanTask
} from '@/lib/clio-kanban'
import { cn } from '@/lib/utils'
import { notify, notifyError } from '@/store/notifications'

import { OverlayView } from '../overlays/overlay-view'

interface KanbanViewProps {
  onClose: () => void
}

const POLL_MS = 5000

/** Status -> accent + glyph. Keeps the board's column headers and card badges
 *  readable at a glance, matching the web dashboard's semantics. */
const STATUS_META: Record<string, { accent: string; glyph: string; label: string }> = {
  blocked: { accent: 'text-red-500', glyph: 'error', label: 'Blocked' },
  done: { accent: 'text-emerald-500', glyph: 'pass-filled', label: 'Done' },
  ready: { accent: 'text-sky-500', glyph: 'play-circle', label: 'Ready' },
  review: { accent: 'text-violet-500', glyph: 'eye', label: 'Review' },
  running: { accent: 'text-blue-500', glyph: 'sync', label: 'Running' },
  scheduled: { accent: 'text-cyan-500', glyph: 'clock', label: 'Scheduled' },
  todo: { accent: 'text-(--ui-text-secondary)', glyph: 'circle-outline', label: 'To do' },
  triage: { accent: 'text-amber-500', glyph: 'inbox', label: 'Triage' }
}

function metaFor(status: string) {
  return STATUS_META[status] ?? { accent: 'text-(--ui-text-secondary)', glyph: 'circle-outline', label: status }
}

const MOVE_TARGETS = ['triage', 'todo', 'ready', 'done'] as const

export function KanbanView({ onClose }: KanbanViewProps) {
  const [board, setBoard] = useState<KanbanBoard | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<null | string>(null)
  const [newTitle, setNewTitle] = useState('')
  const [creating, setCreating] = useState(false)
  const [selectedId, setSelectedId] = useState<null | string>(null)
  const mountedRef = useRef(true)

  const refresh = useCallback(async (showSpinner = false) => {
    if (showSpinner) {setLoading(true)}

    try {
      const next = await getKanbanBoard()

      if (!mountedRef.current) {return}
      setBoard(next)
      setError(null)
    } catch (err) {
      if (!mountedRef.current) {return}
      setError(err instanceof Error ? err.message : 'Failed to load the board')
    } finally {
      if (mountedRef.current) {setLoading(false)}
    }
  }, [])

  useEffect(() => {
    mountedRef.current = true
    void refresh(true)
    const timer = setInterval(() => void refresh(false), POLL_MS)

    return () => {
      mountedRef.current = false
      clearInterval(timer)
    }
  }, [refresh])

  const handleCreate = useCallback(async () => {
    const title = newTitle.trim()

    if (!title || creating) {return}
    setCreating(true)

    try {
      // No assignee + no triage flag -> backend parks it in Triage.
      const res = await createKanbanTask({ title })
      setNewTitle('')

      if (res.warning) {notify({ kind: 'info', message: res.warning, title: 'Kanban' })}
      await refresh(false)
    } catch (err) {
      notifyError(err, 'Could not create the task')
    } finally {
      if (mountedRef.current) {setCreating(false)}
    }
  }, [creating, newTitle, refresh])

  const moveTask = useCallback(
    async (task: KanbanTask, status: string) => {
      if (task.status === status) {return}

      try {
        await updateKanbanTask(task.id, { status })
        await refresh(false)
      } catch (err) {
        notifyError(err, `Could not move task to ${status}`)
      }
    },
    [refresh]
  )

  const columns = board?.columns ?? []
  const selected = columns.flatMap(c => c.tasks).find(t => t.id === selectedId) ?? null

  return (
    <OverlayView closeLabel="Close" onClose={onClose}>
      <div className="flex h-full min-h-0 flex-col" data-testid="kanban-view">
        <header className="flex shrink-0 items-center gap-3 border-b border-(--ui-stroke-tertiary) px-4 py-3">
          <Codicon className="text-(--ui-accent)" name="project" size="1.125rem" />
          <h1 className="text-[0.9375rem] font-semibold">Kanban</h1>
          <div className="flex flex-1 items-center gap-2">
            <Input
              aria-label="New task title"
              className="max-w-md"
              disabled={creating}
              onChange={e => setNewTitle(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter') {void handleCreate()}
              }}
              placeholder="Add a task — lands in Triage for review…"
              value={newTitle}
            />
            <Button disabled={!newTitle.trim() || creating} onClick={() => void handleCreate()} size="sm">
              {creating ? 'Adding…' : 'Add task'}
            </Button>
          </div>
          <Button
            aria-label="Refresh board"
            onClick={() => void refresh(true)}
            size="icon-xs"
            title="Refresh"
            variant="ghost"
          >
            <Codicon name="refresh" size="0.9375rem" />
          </Button>
        </header>

        {error && (
          <div className="shrink-0 border-b border-(--ui-stroke-tertiary) bg-red-500/10 px-4 py-2 text-[0.8125rem] text-red-500">
            {error}
          </div>
        )}

        <div className="flex min-h-0 flex-1">
          <div className="min-h-0 flex-1 overflow-x-auto">
            {loading && !board ? (
              <div className="flex h-full items-center justify-center text-(--ui-text-tertiary)">Loading board…</div>
            ) : columns.every(c => c.tasks.length === 0) ? (
              <div className="flex h-full flex-col items-center justify-center gap-1 text-(--ui-text-tertiary)">
                <Codicon name="inbox" size="1.5rem" />
                <p className="text-[0.8125rem]">No tasks yet. Add one above — it starts in Triage.</p>
              </div>
            ) : (
              <div className="flex h-full items-stretch gap-3 p-3">
                {columns.map(col => (
                  <BoardColumn
                    column={col}
                    key={col.name}
                    onSelect={setSelectedId}
                    selectedId={selectedId}
                  />
                ))}
              </div>
            )}
          </div>

          {selected && (
            <TaskDrawer
              onClose={() => setSelectedId(null)}
              onMove={moveTask}
              task={selected}
            />
          )}
        </div>
      </div>
    </OverlayView>
  )
}

function BoardColumn({
  column,
  onSelect,
  selectedId
}: {
  column: KanbanColumn
  onSelect: (id: string) => void
  selectedId: null | string
}) {
  const meta = metaFor(column.name)

  return (
    <section className="flex w-64 shrink-0 flex-col rounded-lg bg-(--ui-bg-tertiary)/40">
      <div className="flex items-center gap-1.5 px-2.5 py-2">
        <Codicon className={cn('shrink-0', meta.accent)} name={meta.glyph} size="0.8125rem" />
        <span className="text-[0.75rem] font-semibold uppercase tracking-wide text-(--ui-text-secondary)">
          {meta.label}
        </span>
        <span className="ml-auto rounded-full bg-(--ui-bg-quaternary) px-1.5 text-[0.6875rem] tabular-nums text-(--ui-text-tertiary)">
          {column.tasks.length}
        </span>
      </div>
      <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto px-2 pb-2">
        {column.tasks.map(task => (
          <TaskCard isSelected={task.id === selectedId} key={task.id} onSelect={onSelect} task={task} />
        ))}
      </div>
    </section>
  )
}

function TaskCard({
  isSelected,
  onSelect,
  task
}: {
  isSelected: boolean
  onSelect: (id: string) => void
  task: KanbanTask
}) {
  return (
    <button
      className={cn(
        'w-full rounded-md border border-(--ui-stroke-tertiary) bg-(--ui-chat-surface-background) px-2.5 py-2 text-left',
        'hover:border-(--ui-stroke-secondary) hover:bg-(--ui-row-hover-background)',
        isSelected && 'border-(--ui-accent) ring-1 ring-(--ui-accent)'
      )}
      data-testid="kanban-card"
      onClick={() => onSelect(task.id)}
      type="button"
    >
      <p className="line-clamp-3 text-[0.8125rem] font-medium text-foreground">{task.title}</p>
      <div className="mt-1.5 flex items-center gap-2 text-[0.6875rem] text-(--ui-text-tertiary)">
        {task.assignee ? (
          <span className="inline-flex items-center gap-1">
            <Codicon name="account" size="0.75rem" />
            {task.assignee}
          </span>
        ) : (
          <span className="text-(--ui-text-quaternary)">unassigned</span>
        )}
        {task.priority > 0 && <span className="text-amber-500">P{task.priority}</span>}
        {task.progress && (
          <span className="ml-auto tabular-nums">
            {task.progress.done}/{task.progress.total}
          </span>
        )}
      </div>
    </button>
  )
}

function TaskDrawer({
  onClose,
  onMove,
  task
}: {
  onClose: () => void
  onMove: (task: KanbanTask, status: string) => Promise<void>
  task: KanbanTask
}) {
  const meta = metaFor(task.status)

  return (
    <aside
      className="flex w-80 shrink-0 flex-col border-l border-(--ui-stroke-tertiary) bg-(--ui-chat-surface-background)"
      data-testid="kanban-drawer"
    >
      <div className="flex items-center gap-2 border-b border-(--ui-stroke-tertiary) px-3 py-2">
        <Codicon className={meta.accent} name={meta.glyph} size="0.875rem" />
        <span className={cn('text-[0.6875rem] font-semibold uppercase tracking-wide', meta.accent)}>{meta.label}</span>
        <Button aria-label="Close details" className="ml-auto" onClick={onClose} size="icon-xs" variant="ghost">
          <Codicon name="close" size="0.8125rem" />
        </Button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-3">
        <h2 className="text-[0.875rem] font-semibold text-foreground">{task.title}</h2>
        {task.body && <p className="mt-2 whitespace-pre-wrap text-[0.8125rem] text-(--ui-text-secondary)">{task.body}</p>}
        {task.latest_summary && (
          <p className="mt-3 rounded bg-(--ui-bg-tertiary) p-2 text-[0.75rem] text-(--ui-text-tertiary)">
            {task.latest_summary}
          </p>
        )}
        <dl className="mt-3 space-y-1 text-[0.75rem] text-(--ui-text-tertiary)">
          <div className="flex justify-between">
            <dt>Assignee</dt>
            <dd className="text-(--ui-text-secondary)">{task.assignee || 'unassigned'}</dd>
          </div>
          <div className="flex justify-between">
            <dt>Priority</dt>
            <dd className="text-(--ui-text-secondary)">{task.priority}</dd>
          </div>
          {task.tenant && (
            <div className="flex justify-between">
              <dt>Tenant</dt>
              <dd className="text-(--ui-text-secondary)">{task.tenant}</dd>
            </div>
          )}
        </dl>
      </div>
      <div className="shrink-0 border-t border-(--ui-stroke-tertiary) px-3 py-2">
        <p className="mb-1.5 text-[0.6875rem] uppercase tracking-wide text-(--ui-text-tertiary)">Move to</p>
        <div className="flex flex-wrap gap-1.5">
          {MOVE_TARGETS.map(target => (
            <Button
              disabled={task.status === target}
              key={target}
              onClick={() => void onMove(task, target)}
              size="sm"
              variant={task.status === target ? 'secondary' : 'outline'}
            >
              {metaFor(target).label}
            </Button>
          ))}
        </div>
      </div>
    </aside>
  )
}
