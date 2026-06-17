import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Codicon } from '@/components/ui/codicon'
import { Input } from '@/components/ui/input'
import {
  addKanbanComment,
  archiveKanbanTask,
  createKanbanTask,
  decomposeKanbanTask,
  dispatchKanban,
  getKanbanBoard,
  getKanbanOrchestration,
  getKanbanProfiles,
  getKanbanTaskDetail,
  getKanbanWorkers,
  type KanbanBoard,
  type KanbanColumn,
  type KanbanProfile,
  type KanbanTask,
  type KanbanTaskDetail,
  type KanbanWorker,
  reassignKanbanTask,
  reclaimKanbanTask,
  specifyKanbanTask,
  terminateKanbanRun,
  updateKanbanTask
} from '@/lib/clio-kanban'
import { cn } from '@/lib/utils'
import { notify, notifyError } from '@/store/notifications'

import { OverlayView } from '../overlays/overlay-view'

interface KanbanViewProps {
  onClose: () => void
}

type Tab = 'board' | 'profiles' | 'workers'

const POLL_MS = 5000

/** Status -> accent + glyph + label, matching the web dashboard's semantics. */
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
  const [tab, setTab] = useState<Tab>('board')
  const [newTitle, setNewTitle] = useState('')
  const [creating, setCreating] = useState(false)
  const [selectedId, setSelectedId] = useState<null | string>(null)
  const [search, setSearch] = useState('')
  const [tenant, setTenant] = useState('')
  const [assignee, setAssignee] = useState('')
  const mountedRef = useRef(true)

  const refresh = useCallback(
    async (showSpinner = false, tenantFilter = '') => {
      if (showSpinner) {setLoading(true)}

      try {
        const next = await getKanbanBoard(tenantFilter || undefined)

        if (!mountedRef.current) {return}
        setBoard(next)
        setError(null)
      } catch (err) {
        if (!mountedRef.current) {return}
        setError(err instanceof Error ? err.message : 'Failed to load the board')
      } finally {
        if (mountedRef.current) {setLoading(false)}
      }
    },
    []
  )

  useEffect(() => {
    mountedRef.current = true
    void refresh(true, tenant)
    const timer = setInterval(() => void refresh(false, tenant), POLL_MS)

    return () => {
      mountedRef.current = false
      clearInterval(timer)
    }
  }, [refresh, tenant])

  const handleCreate = useCallback(async () => {
    const title = newTitle.trim()

    if (!title || creating) {return}
    setCreating(true)

    try {
      const res = await createKanbanTask({ title })
      setNewTitle('')

      if (res.warning) {notify({ kind: 'info', message: res.warning, title: 'Kanban' })}
      await refresh(false, tenant)
    } catch (err) {
      notifyError(err, 'Could not create the task')
    } finally {
      if (mountedRef.current) {setCreating(false)}
    }
  }, [creating, newTitle, refresh, tenant])

  const moveTask = useCallback(
    async (task: KanbanTask, status: string) => {
      if (task.status === status) {return}

      try {
        await updateKanbanTask(task.id, { status })
        await refresh(false, tenant)
      } catch (err) {
        notifyError(err, `Could not move task to ${status}`)
      }
    },
    [refresh, tenant]
  )

  const runTaskAction = useCallback(
    async (label: string, fn: () => Promise<unknown>) => {
      try {
        const res = (await fn()) as { ok?: boolean; reason?: string } | undefined

        if (res && res.ok === false) {
          notify({ kind: 'info', message: res.reason || `${label} not applicable`, title: 'Kanban' })
        }

        await refresh(false, tenant)
      } catch (err) {
        notifyError(err, `${label} failed`)
      }
    },
    [refresh, tenant]
  )

  const dispatchNudge = useCallback(
    async (dryRun: boolean) => {
      try {
        await dispatchKanban({ dryRun, max: 4 })
        notify({ kind: 'success', message: dryRun ? 'Dry run complete' : 'Nudged the dispatcher', title: 'Kanban' })
        await refresh(false, tenant)
      } catch (err) {
        notifyError(err, 'Dispatch failed')
      }
    },
    [refresh, tenant]
  )

  const allAssignees = board?.assignees ?? []
  const allTenants = board?.tenants ?? []
  const columns = board?.columns ?? []

  // Client-side search + assignee filter (tenant is server-side via re-fetch).
  const filteredColumns = useMemo<KanbanColumn[]>(() => {
    const q = search.trim().toLowerCase()

    return columns.map(col => ({
      ...col,
      tasks: col.tasks.filter(t => {
        if (assignee && t.assignee !== assignee) {return false}

        if (!q) {return true}

        return (
          t.title.toLowerCase().includes(q) ||
          (t.body ?? '').toLowerCase().includes(q) ||
          (t.assignee ?? '').toLowerCase().includes(q) ||
          (t.latest_summary ?? '').toLowerCase().includes(q)
        )
      })
    }))
  }, [columns, search, assignee])

  const selected = columns.flatMap(c => c.tasks).find(t => t.id === selectedId) ?? null

  return (
    <OverlayView closeLabel="Close" onClose={onClose}>
      <div className="flex h-full min-h-0 flex-col" data-testid="kanban-view">
        {/* Top padding clears OverlayView's draggable titlebar strip — without it
            the OS eats the toolbar's focus/clicks. Do NOT add app-region:drag. */}
        <header className="flex shrink-0 flex-col gap-2 border-b border-(--ui-stroke-tertiary) px-4 pb-2 pt-[calc(var(--titlebar-height)+0.5rem)]">
          <div className="flex items-center gap-3">
            <Codicon className="text-(--ui-accent)" name="project" size="1.125rem" />
            <h1 className="text-[0.9375rem] font-semibold">Kanban</h1>
            <div className="flex items-center gap-1 rounded-lg bg-(--ui-bg-tertiary)/60 p-0.5">
              {(['board', 'workers', 'profiles'] as const).map(t => (
                <button
                  className={cn(
                    'rounded-md px-2.5 py-1 text-[0.75rem] font-medium capitalize',
                    tab === t ? 'bg-(--ui-control-active-background) text-foreground' : 'text-(--ui-text-tertiary) hover:text-foreground'
                  )}
                  key={t}
                  onClick={() => setTab(t)}
                  type="button"
                >
                  {t}
                </button>
              ))}
            </div>
            <div className="ml-auto flex items-center gap-1.5">
              <Button onClick={() => void dispatchNudge(true)} size="sm" title="Dry run dispatch" variant="ghost">
                Dry run
              </Button>
              <Button onClick={() => void dispatchNudge(false)} size="sm" title="Nudge the dispatcher" variant="outline">
                Nudge
              </Button>
              <Button aria-label="Refresh" onClick={() => void refresh(true, tenant)} size="icon-xs" title="Refresh" variant="ghost">
                <Codicon name="refresh" size="0.9375rem" />
              </Button>
            </div>
          </div>

          {tab === 'board' && (
            <div className="flex flex-wrap items-center gap-2">
              <Input
                aria-label="New task title"
                className="min-w-[16rem] flex-1"
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
              <Input
                aria-label="Search tasks"
                className="w-44"
                onChange={e => setSearch(e.target.value)}
                placeholder="Search…"
                value={search}
              />
              {allAssignees.length > 0 && (
                <FilterSelect
                  ariaLabel="Filter by assignee"
                  onChange={setAssignee}
                  options={allAssignees}
                  placeholder="All assignees"
                  value={assignee}
                />
              )}
              {allTenants.length > 0 && (
                <FilterSelect
                  ariaLabel="Filter by tenant"
                  onChange={setTenant}
                  options={allTenants}
                  placeholder="All tenants"
                  value={tenant}
                />
              )}
            </div>
          )}
        </header>

        {error && (
          <div className="shrink-0 border-b border-(--ui-stroke-tertiary) bg-red-500/10 px-4 py-2 text-[0.8125rem] text-red-500">
            {error}
          </div>
        )}

        {tab === 'board' && (
          <div className="flex min-h-0 flex-1">
            <div className="min-h-0 flex-1 overflow-x-auto">
              {loading && !board ? (
                <div className="flex h-full items-center justify-center text-(--ui-text-tertiary)">Loading board…</div>
              ) : (
                <div className="flex h-full items-stretch gap-3 p-3">
                  {filteredColumns.map(col => (
                    <BoardColumn column={col} key={col.name} onSelect={setSelectedId} selectedId={selectedId} />
                  ))}
                </div>
              )}
            </div>

            {selected && (
              <TaskDrawer
                onArchive={() => void runTaskAction('Archive', () => archiveKanbanTask(selected.id)).then(() => setSelectedId(null))}
                onClose={() => setSelectedId(null)}
                onComment={text => addKanbanComment(selected.id, text)}
                onDecompose={() => void runTaskAction('Decompose', () => decomposeKanbanTask(selected.id))}
                onMove={moveTask}
                onReassign={a => void runTaskAction('Reassign', () => reassignKanbanTask(selected.id, a))}
                onReclaim={() => void runTaskAction('Reclaim', () => reclaimKanbanTask(selected.id))}
                onSpecify={() => void runTaskAction('Specify', () => specifyKanbanTask(selected.id))}
                task={selected}
              />
            )}
          </div>
        )}

        {tab === 'workers' && <WorkersPanel onChanged={() => void refresh(false, tenant)} />}
        {tab === 'profiles' && <ProfilesPanel />}
      </div>
    </OverlayView>
  )
}

function FilterSelect({
  ariaLabel,
  onChange,
  options,
  placeholder,
  value
}: {
  ariaLabel: string
  onChange: (value: string) => void
  options: string[]
  placeholder: string
  value: string
}) {
  return (
    <select
      aria-label={ariaLabel}
      className="h-7 rounded-md border border-(--ui-stroke-tertiary) bg-(--ui-bg-tertiary) px-2 text-[0.75rem] text-foreground"
      onChange={e => onChange(e.target.value)}
      value={value}
    >
      <option value="">{placeholder}</option>
      {options.map(o => (
        <option key={o} value={o}>
          {o}
        </option>
      ))}
    </select>
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
        <span className="text-[0.75rem] font-semibold uppercase tracking-wide text-(--ui-text-secondary)">{meta.label}</span>
        <span className="ml-auto rounded-full bg-(--ui-bg-quaternary) px-1.5 text-[0.6875rem] tabular-nums text-(--ui-text-tertiary)">
          {column.tasks.length}
        </span>
      </div>
      <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto px-2 pb-2">
        {column.tasks.length === 0 ? (
          <p className="px-1 py-2 text-[0.6875rem] text-(--ui-text-quaternary)">No tasks</p>
        ) : (
          column.tasks.map(task => (
            <TaskCard isSelected={task.id === selectedId} key={task.id} onSelect={onSelect} task={task} />
          ))
        )}
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
  const hasWarnings = (task.warnings?.length ?? 0) > 0

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
      {task.latest_summary && (
        <p className="mt-1 line-clamp-2 text-[0.6875rem] text-(--ui-text-tertiary)">{task.latest_summary}</p>
      )}
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
        {hasWarnings && <Codicon className="text-amber-500" name="warning" size="0.75rem" />}
        {(task.comment_count ?? 0) > 0 && (
          <span className="inline-flex items-center gap-0.5">
            <Codicon name="comment" size="0.75rem" />
            {task.comment_count}
          </span>
        )}
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
  onArchive,
  onClose,
  onComment,
  onDecompose,
  onMove,
  onReassign,
  onReclaim,
  onSpecify,
  task
}: {
  onArchive: () => void
  onClose: () => void
  onComment: (text: string) => Promise<unknown>
  onDecompose: () => void
  onMove: (task: KanbanTask, status: string) => Promise<void>
  onReassign: (assignee: string) => void
  onReclaim: () => void
  onSpecify: () => void
  task: KanbanTask
}) {
  const meta = metaFor(task.status)
  const [detail, setDetail] = useState<KanbanTaskDetail | null>(null)
  const [commentText, setCommentText] = useState('')
  const [reassignTo, setReassignTo] = useState('')
  const [posting, setPosting] = useState(false)

  const loadDetail = useCallback(async () => {
    try {
      setDetail(await getKanbanTaskDetail(task.id))
    } catch {
      /* drawer still shows the card-level data */
    }
  }, [task.id])

  useEffect(() => {
    void loadDetail()
  }, [loadDetail])

  const submitComment = useCallback(async () => {
    const text = commentText.trim()

    if (!text || posting) {return}
    setPosting(true)

    try {
      await onComment(text)
      setCommentText('')
      await loadDetail()
    } catch (err) {
      notifyError(err, 'Could not add the comment')
    } finally {
      setPosting(false)
    }
  }, [commentText, posting, onComment, loadDetail])

  const body = detail?.task.body ?? task.body
  const comments = detail?.comments ?? []
  const runs = detail?.runs ?? []
  const events = detail?.events ?? []

  return (
    <aside
      className="flex w-96 shrink-0 flex-col border-l border-(--ui-stroke-tertiary) bg-(--ui-chat-surface-background)"
      data-testid="kanban-drawer"
    >
      <div className="flex items-center gap-2 border-b border-(--ui-stroke-tertiary) px-3 py-2">
        <Codicon className={meta.accent} name={meta.glyph} size="0.875rem" />
        <span className={cn('text-[0.6875rem] font-semibold uppercase tracking-wide', meta.accent)}>{meta.label}</span>
        <Button aria-label="Close details" className="ml-auto" onClick={onClose} size="icon-xs" variant="ghost">
          <Codicon name="close" size="0.8125rem" />
        </Button>
      </div>

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-3 py-3">
        <h2 className="text-[0.875rem] font-semibold text-foreground">{task.title}</h2>
        {body && <p className="whitespace-pre-wrap text-[0.8125rem] text-(--ui-text-secondary)">{body}</p>}
        {task.latest_summary && (
          <div>
            <DrawerLabel>Latest summary</DrawerLabel>
            <p className="rounded bg-(--ui-bg-tertiary) p-2 text-[0.75rem] text-(--ui-text-tertiary)">{task.latest_summary}</p>
          </div>
        )}
        {(task.warnings?.length ?? 0) > 0 && (
          <div className="rounded border border-amber-500/30 bg-amber-500/10 p-2 text-[0.75rem] text-amber-500">
            {task.warnings!.map((w, i) => (
              <p key={i}>⚠ {w}</p>
            ))}
          </div>
        )}

        <dl className="space-y-1 text-[0.75rem] text-(--ui-text-tertiary)">
          <Row label="Assignee">{task.assignee || 'unassigned'}</Row>
          <Row label="Priority">{String(task.priority)}</Row>
          {task.tenant && <Row label="Tenant">{task.tenant}</Row>}
        </dl>

        {/* Comments */}
        <div>
          <DrawerLabel>Comments ({comments.length})</DrawerLabel>
          <div className="space-y-1.5">
            {comments.map((c, i) => (
              <div className="rounded bg-(--ui-bg-tertiary) p-2 text-[0.75rem]" key={c.id ?? i}>
                {c.author && <span className="font-medium text-(--ui-text-secondary)">{c.author}: </span>}
                <span className="text-(--ui-text-tertiary)">{c.text}</span>
              </div>
            ))}
          </div>
          <div className="mt-1.5 flex gap-1.5">
            <Input
              aria-label="New comment"
              className="flex-1"
              onChange={e => setCommentText(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter') {void submitComment()}
              }}
              placeholder="Add a comment…"
              value={commentText}
            />
            <Button disabled={!commentText.trim() || posting} onClick={() => void submitComment()} size="sm" variant="outline">
              Post
            </Button>
          </div>
        </div>

        {/* Run history */}
        {runs.length > 0 && (
          <div>
            <DrawerLabel>Run history</DrawerLabel>
            <div className="space-y-1">
              {runs.map((r, i) => (
                <div className="flex items-center gap-2 text-[0.6875rem] text-(--ui-text-tertiary)" key={r.run_id ?? i}>
                  <span className="tabular-nums">{r.run_id?.slice(0, 8)}</span>
                  <span>{r.outcome || r.status}</span>
                  {r.summary && <span className="truncate">— {r.summary}</span>}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Recent events */}
        {events.length > 0 && (
          <div>
            <DrawerLabel>Recent events</DrawerLabel>
            <div className="space-y-0.5">
              {events.slice(-8).map((ev, i) => (
                <p className="text-[0.6875rem] text-(--ui-text-quaternary)" key={ev.id ?? i}>
                  {ev.kind}
                  {ev.detail ? ` — ${ev.detail}` : ''}
                </p>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="shrink-0 space-y-2 border-t border-(--ui-stroke-tertiary) px-3 py-2">
        <div>
          <DrawerLabel>Move to</DrawerLabel>
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
            <Button
              onClick={() => void onMove(task, task.status === 'blocked' ? 'ready' : 'blocked')}
              size="sm"
              variant="outline"
            >
              {task.status === 'blocked' ? 'Unblock' : 'Block'}
            </Button>
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {task.status === 'triage' && (
            <>
              <Button onClick={onSpecify} size="sm" variant="outline">
                Specify
              </Button>
              <Button onClick={onDecompose} size="sm" variant="outline">
                Decompose
              </Button>
            </>
          )}
          <Button onClick={onReclaim} size="sm" variant="outline">
            Reclaim
          </Button>
          <Button onClick={onArchive} size="sm" variant="ghost">
            Archive
          </Button>
        </div>
        <div className="flex gap-1.5">
          <Input
            aria-label="Reassign to"
            className="flex-1"
            onChange={e => setReassignTo(e.target.value)}
            placeholder="Reassign to profile…"
            value={reassignTo}
          />
          <Button
            disabled={!reassignTo.trim()}
            onClick={() => {
              onReassign(reassignTo.trim())
              setReassignTo('')
            }}
            size="sm"
            variant="outline"
          >
            Reassign
          </Button>
        </div>
      </div>
    </aside>
  )
}

function WorkersPanel({ onChanged }: { onChanged: () => void }) {
  const [workers, setWorkers] = useState<KanbanWorker[] | null>(null)

  const load = useCallback(async () => {
    try {
      const res = await getKanbanWorkers()
      setWorkers(res.workers ?? [])
    } catch {
      setWorkers([])
    }
  }, [])

  useEffect(() => {
    void load()
    const timer = setInterval(() => void load(), POLL_MS)

    return () => clearInterval(timer)
  }, [load])

  const terminate = useCallback(
    async (runId: string) => {
      try {
        await terminateKanbanRun(runId)
        notify({ kind: 'success', message: 'Worker terminated', title: 'Kanban' })
        await load()
        onChanged()
      } catch (err) {
        notifyError(err, 'Could not terminate the worker')
      }
    },
    [load, onChanged]
  )

  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-4" data-testid="kanban-workers">
      <h2 className="mb-3 text-[0.875rem] font-semibold">Active workers</h2>
      {!workers ? (
        <p className="text-(--ui-text-tertiary)">Loading…</p>
      ) : workers.length === 0 ? (
        <p className="text-[0.8125rem] text-(--ui-text-tertiary)">No workers are running right now.</p>
      ) : (
        <div className="space-y-2">
          {workers.map(w => (
            <div
              className="flex items-center gap-3 rounded-lg border border-(--ui-stroke-tertiary) bg-(--ui-chat-surface-background) px-3 py-2"
              key={w.run_id}
            >
              <Codicon className="text-blue-500" name="sync" size="0.875rem" spinning />
              <div className="min-w-0 flex-1 text-[0.75rem]">
                <p className="text-(--ui-text-secondary)">
                  Run {w.run_id?.slice(0, 8)} · PID {w.worker_pid ?? 'n/a'} · {w.profile || w.task_assignee || 'unassigned'}
                </p>
                {w.task_id && <p className="text-(--ui-text-tertiary)">Task {w.task_id}</p>}
              </div>
              <Button onClick={() => void terminate(w.run_id)} size="sm" variant="outline">
                Terminate
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function ProfilesPanel() {
  const [profiles, setProfiles] = useState<KanbanProfile[] | null>(null)
  const [orchestration, setOrchestration] = useState<{ resolved_default_assignee?: string } | null>(null)

  useEffect(() => {
    void (async () => {
      try {
        const [p, o] = await Promise.all([getKanbanProfiles(), getKanbanOrchestration().catch(() => ({}))])
        setProfiles(p.profiles ?? [])
        setOrchestration(o)
      } catch {
        setProfiles([])
      }
    })()
  }, [])

  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-4" data-testid="kanban-profiles">
      <h2 className="mb-1 text-[0.875rem] font-semibold">Profiles &amp; routing</h2>
      <p className="mb-3 text-[0.75rem] text-(--ui-text-tertiary)">
        Default assignee: <span className="text-(--ui-text-secondary)">{orchestration?.resolved_default_assignee || 'active profile'}</span>
      </p>
      {!profiles ? (
        <p className="text-(--ui-text-tertiary)">Loading…</p>
      ) : (
        <div className="space-y-2">
          {profiles.map(p => (
            <div className="rounded-lg border border-(--ui-stroke-tertiary) bg-(--ui-chat-surface-background) px-3 py-2" key={p.name}>
              <div className="flex items-center gap-2">
                <span className="text-[0.8125rem] font-semibold">{p.name}</span>
                {p.is_default && (
                  <span className="rounded-full bg-(--ui-accent)/15 px-1.5 text-[0.625rem] text-(--ui-accent)">default</span>
                )}
                {p.skill_count != null && (
                  <span className="ml-auto text-[0.6875rem] text-(--ui-text-tertiary)">{p.skill_count} skills</span>
                )}
              </div>
              {(p.model || p.provider) && (
                <p className="mt-0.5 text-[0.6875rem] text-(--ui-text-tertiary)">
                  {p.provider}
                  {p.provider && p.model ? ' · ' : ''}
                  {p.model}
                </p>
              )}
              {p.description && <p className="mt-1 text-[0.75rem] text-(--ui-text-secondary)">{p.description}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function DrawerLabel({ children }: { children: React.ReactNode }) {
  return <p className="mb-1 text-[0.625rem] font-semibold uppercase tracking-wide text-(--ui-text-quaternary)">{children}</p>
}

function Row({ children, label }: { children: React.ReactNode; label: string }) {
  return (
    <div className="flex justify-between">
      <dt>{label}</dt>
      <dd className="text-(--ui-text-secondary)">{children}</dd>
    </div>
  )
}
