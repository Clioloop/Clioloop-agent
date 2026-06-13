/**
 * Desktop client for the Kanban dashboard plugin REST API
 * (``/api/plugins/kanban/*``, served by the same backend that serves
 * ``/api/sessions`` etc.). This mirrors the web dashboard's Kanban surface so
 * the desktop board behaves identically — including the "bare task → triage"
 * routing default.
 */

export interface KanbanTask {
  assignee?: null | string
  body?: null | string
  comment_count?: number
  created_at?: number
  id: string
  latest_summary?: null | string
  link_counts?: { children: number; parents: number }
  priority: number
  progress?: null | { done: number; total: number }
  status: string
  tenant?: null | string
  title: string
  warnings?: null | string[]
}

export interface KanbanColumn {
  name: string
  tasks: KanbanTask[]
}

export interface KanbanBoard {
  assignees: string[]
  columns: KanbanColumn[]
  latest_event_id: number
  tenants: string[]
}

export interface KanbanComment {
  author?: null | string
  created_at?: number
  id?: number
  text: string
}

export interface KanbanRun {
  ended_at?: null | number
  outcome?: null | string
  run_id: string
  started_at?: number
  status?: string
  summary?: null | string
  worker_pid?: null | number
}

export interface KanbanEvent {
  created_at?: number
  detail?: string
  id?: number
  kind?: string
}

export interface KanbanTaskDetail {
  comments: KanbanComment[]
  events: KanbanEvent[]
  links?: { children: string[]; parents: string[] }
  runs: KanbanRun[]
  task: KanbanTask
}

export interface KanbanWorker {
  profile?: null | string
  run_id: string
  started_at?: number
  task_assignee?: null | string
  task_id?: string
  worker_pid?: null | number
}

export interface KanbanProfile {
  description?: string
  description_auto?: boolean
  is_default?: boolean
  model?: string
  name: string
  provider?: string
  skill_count?: number
}

export interface CreateKanbanTaskBody {
  assignee?: string
  body?: string
  priority?: number
  /** Omit to use the backend default (bare task → triage). */
  triage?: boolean
}

export interface UpdateKanbanTaskBody {
  assignee?: null | string
  block_reason?: string
  priority?: number
  result?: string
  status?: string
  title?: string
}

const BASE = '/api/plugins/kanban'

function api<T>(path: string, init?: { body?: unknown; method?: string }): Promise<T> {
  return window.clioDesktop.api<T>({ body: init?.body, method: init?.method, path: `${BASE}${path}` })
}

const enc = encodeURIComponent

export function getKanbanBoard(tenant?: string): Promise<KanbanBoard> {
  return api<KanbanBoard>(tenant ? `/board?tenant=${enc(tenant)}` : '/board')
}

export function getKanbanTaskDetail(id: string): Promise<KanbanTaskDetail> {
  return api<KanbanTaskDetail>(`/tasks/${enc(id)}`)
}

export function createKanbanTask(
  body: CreateKanbanTaskBody & { title: string }
): Promise<{ task: KanbanTask; warning?: string }> {
  return api('/tasks', { body, method: 'POST' })
}

export function updateKanbanTask(id: string, body: UpdateKanbanTaskBody): Promise<{ task: KanbanTask }> {
  return api(`/tasks/${enc(id)}`, { body, method: 'PATCH' })
}

/** Archive = a status transition the board hides; matches the dashboard. */
export function archiveKanbanTask(id: string): Promise<{ task: KanbanTask }> {
  return updateKanbanTask(id, { status: 'archived' })
}

export function addKanbanComment(id: string, text: string): Promise<unknown> {
  return api(`/tasks/${enc(id)}/comments`, { body: { text }, method: 'POST' })
}

export function specifyKanbanTask(id: string): Promise<{ ok: boolean; reason?: string }> {
  return api(`/tasks/${enc(id)}/specify`, { body: {}, method: 'POST' })
}

export function decomposeKanbanTask(id: string): Promise<{ ok: boolean; reason?: string }> {
  return api(`/tasks/${enc(id)}/decompose`, { body: {}, method: 'POST' })
}

export function reclaimKanbanTask(id: string): Promise<{ ok: boolean }> {
  return api(`/tasks/${enc(id)}/reclaim`, { body: {}, method: 'POST' })
}

export function reassignKanbanTask(id: string, assignee: string): Promise<{ ok: boolean }> {
  return api(`/tasks/${enc(id)}/reassign`, { body: { assignee }, method: 'POST' })
}

export function dispatchKanban(opts: { dryRun?: boolean; max?: number } = {}): Promise<unknown> {
  const params = new URLSearchParams()
  params.set('dry_run', String(Boolean(opts.dryRun)))

  if (opts.max != null) {params.set('max', String(opts.max))}

  return api(`/dispatch?${params.toString()}`, { body: {}, method: 'POST' })
}

export function getKanbanWorkers(): Promise<{ workers: KanbanWorker[] }> {
  return api<{ workers: KanbanWorker[] }>('/workers/active')
}

export function terminateKanbanRun(runId: string): Promise<{ ok: boolean }> {
  return api(`/runs/${enc(runId)}/terminate`, { body: {}, method: 'POST' })
}

export function getKanbanProfiles(): Promise<{ profiles: KanbanProfile[] }> {
  return api<{ profiles: KanbanProfile[] }>('/profiles')
}

export function getKanbanOrchestration(): Promise<{ default_assignee?: string; resolved_default_assignee?: string }> {
  return api('/orchestration')
}
