/**
 * Desktop client for the Kanban dashboard plugin REST API
 * (``/api/plugins/kanban/*``, served by the same backend that serves
 * ``/api/sessions`` etc.). This is the same surface the web dashboard's
 * Kanban board uses, so the desktop board behaves identically — including the
 * "bare task → triage" routing default.
 */

export interface KanbanTask {
  assignee?: null | string
  body?: null | string
  comment_count?: number
  created_at?: number
  id: string
  latest_summary?: null | string
  priority: number
  progress?: null | { done: number; total: number }
  status: string
  tenant?: null | string
  title: string
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

export interface CreateKanbanTaskBody {
  assignee?: string
  body?: string
  priority?: number
  /** Omit to use the backend default (bare task → triage). */
  triage?: boolean
}

export interface UpdateKanbanTaskBody {
  assignee?: null | string
  priority?: number
  status?: string
  title?: string
}

function api<T>(path: string, init?: { body?: unknown; method?: string }): Promise<T> {
  return window.clioDesktop.api<T>({ body: init?.body, method: init?.method, path })
}

export function getKanbanBoard(): Promise<KanbanBoard> {
  return api<KanbanBoard>('/api/plugins/kanban/board')
}

export function createKanbanTask(
  body: CreateKanbanTaskBody & { title: string }
): Promise<{ task: KanbanTask; warning?: string }> {
  return api('/api/plugins/kanban/tasks', { body, method: 'POST' })
}

export function updateKanbanTask(id: string, body: UpdateKanbanTaskBody): Promise<{ task: KanbanTask }> {
  return api(`/api/plugins/kanban/tasks/${encodeURIComponent(id)}`, { body, method: 'PATCH' })
}
