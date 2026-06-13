// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { KanbanBoard, KanbanTaskDetail } from '@/lib/clio-kanban'

import { KanbanView } from './index'

const k = vi.hoisted(() => ({
  addKanbanComment: vi.fn(),
  archiveKanbanTask: vi.fn(),
  createKanbanTask: vi.fn(),
  decomposeKanbanTask: vi.fn(),
  dispatchKanban: vi.fn(),
  getKanbanBoard: vi.fn(),
  getKanbanOrchestration: vi.fn(),
  getKanbanProfiles: vi.fn(),
  getKanbanTaskDetail: vi.fn(),
  getKanbanWorkers: vi.fn(),
  reassignKanbanTask: vi.fn(),
  reclaimKanbanTask: vi.fn(),
  specifyKanbanTask: vi.fn(),
  terminateKanbanRun: vi.fn(),
  updateKanbanTask: vi.fn()
}))

vi.mock('@/lib/clio-kanban', () => k)

function board(): KanbanBoard {
  return {
    assignees: ['alice', 'bob'],
    columns: [
      { name: 'triage', tasks: [{ assignee: null, id: 't1', priority: 0, status: 'triage', title: 'Triage me' }] },
      { name: 'todo', tasks: [] },
      { name: 'ready', tasks: [{ assignee: 'alice', id: 't2', priority: 2, status: 'ready', title: 'Ready task' }] },
      { name: 'done', tasks: [] }
    ],
    latest_event_id: 5,
    tenants: []
  }
}

function detail(): KanbanTaskDetail {
  return {
    comments: [{ author: 'bob', id: 1, text: 'looks good' }],
    events: [{ detail: 'created', id: 1, kind: 'created' }],
    links: { children: [], parents: [] },
    runs: [{ outcome: 'completed', run_id: 'run12345', summary: 'did the thing' }],
    task: { body: 'task body text', id: 't1', priority: 0, status: 'triage', title: 'Triage me' }
  }
}

describe('KanbanView', () => {
  beforeEach(() => {
    k.getKanbanBoard.mockResolvedValue(board())
    k.getKanbanTaskDetail.mockResolvedValue(detail())
    k.createKanbanTask.mockResolvedValue({ task: { id: 't3', priority: 0, status: 'triage', title: 'New' } })
    k.updateKanbanTask.mockResolvedValue({ task: { id: 't1', priority: 0, status: 'done', title: 'Triage me' } })
    k.archiveKanbanTask.mockResolvedValue({ task: { id: 't1', priority: 0, status: 'archived', title: 'Triage me' } })
    k.addKanbanComment.mockResolvedValue({})
    k.specifyKanbanTask.mockResolvedValue({ ok: true })
    k.decomposeKanbanTask.mockResolvedValue({ ok: true })
    k.reclaimKanbanTask.mockResolvedValue({ ok: true })
    k.reassignKanbanTask.mockResolvedValue({ ok: true })
    k.dispatchKanban.mockResolvedValue({})
    k.getKanbanWorkers.mockResolvedValue({ workers: [] })
    k.terminateKanbanRun.mockResolvedValue({ ok: true })
    k.getKanbanProfiles.mockResolvedValue({ profiles: [] })
    k.getKanbanOrchestration.mockResolvedValue({})
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('renders columns and cards from the board API', async () => {
    render(<KanbanView onClose={() => {}} />)
    expect(await screen.findByText('Triage me')).toBeTruthy()
    expect(screen.getByText('Ready task')).toBeTruthy()
    expect(screen.getByText('Triage')).toBeTruthy()
    expect(screen.getByText('Ready')).toBeTruthy()
    // 'alice' appears on the card and in the assignee filter option — both fine.
    expect(screen.getAllByText('alice').length).toBeGreaterThan(0)
  })

  it('renders ALL default columns even when the board is empty (no full-page state)', async () => {
    k.getKanbanBoard.mockResolvedValue({
      assignees: [],
      columns: ['triage', 'todo', 'scheduled', 'ready', 'running', 'blocked', 'review', 'done'].map(name => ({
        name,
        tasks: []
      })),
      latest_event_id: 0,
      tenants: []
    })
    render(<KanbanView onClose={() => {}} />)
    expect(await screen.findByText('Triage')).toBeTruthy()

    for (const label of ['To do', 'Scheduled', 'Ready', 'Running', 'Blocked', 'Review', 'Done']) {
      expect(screen.getByText(label)).toBeTruthy()
    }

    expect(screen.getAllByText('No tasks').length).toBeGreaterThan(1)
    expect(screen.queryByText(/No tasks yet/)).toBeNull()
  })

  it('lets you type in the new-task input and submit it (no triage flag → backend triage)', async () => {
    render(<KanbanView onClose={() => {}} />)
    await screen.findByText('Triage me')
    const input = screen.getByLabelText('New task title') as HTMLInputElement
    fireEvent.change(input, { target: { value: 'Typed task' } })
    expect(input.value).toBe('Typed task')
    fireEvent.keyDown(input, { key: 'Enter' })
    await waitFor(() => expect(k.createKanbanTask).toHaveBeenCalledWith({ title: 'Typed task' }))
  })

  it('search filters visible cards without hiding columns', async () => {
    render(<KanbanView onClose={() => {}} />)
    await screen.findByText('Triage me')
    fireEvent.change(screen.getByLabelText('Search tasks'), { target: { value: 'ready' } })
    // Matching card stays; non-matching card hidden; columns still present.
    expect(screen.getByText('Ready task')).toBeTruthy()
    expect(screen.queryByText('Triage me')).toBeNull()
    expect(screen.getByText('Triage')).toBeTruthy()
    expect(screen.getByText('Ready')).toBeTruthy()
  })

  it('assignee filter reduces cards', async () => {
    render(<KanbanView onClose={() => {}} />)
    await screen.findByText('Triage me')
    fireEvent.change(screen.getByLabelText('Filter by assignee'), { target: { value: 'alice' } })
    expect(screen.getByText('Ready task')).toBeTruthy()
    expect(screen.queryByText('Triage me')).toBeNull()
  })

  it('nudge button calls dispatch', async () => {
    render(<KanbanView onClose={() => {}} />)
    await screen.findByText('Triage me')
    fireEvent.click(screen.getByText('Nudge'))
    await waitFor(() => expect(k.dispatchKanban).toHaveBeenCalledWith({ dryRun: false, max: 4 }))
  })

  it('opens the drawer, loads detail, comments, moves, specify/reclaim/archive', async () => {
    render(<KanbanView onClose={() => {}} />)
    fireEvent.click(await screen.findByText('Triage me'))
    const drawer = await screen.findByTestId('kanban-drawer')

    // Detail loaded: body + comment + run history.
    await waitFor(() => expect(within(drawer).getByText('task body text')).toBeTruthy())
    expect(within(drawer).getByText(/looks good/)).toBeTruthy()
    expect(within(drawer).getByText(/did the thing/)).toBeTruthy()

    // Add a comment.
    fireEvent.change(within(drawer).getByLabelText('New comment'), { target: { value: 'nice' } })
    fireEvent.click(within(drawer).getByText('Post'))
    await waitFor(() => expect(k.addKanbanComment).toHaveBeenCalledWith('t1', 'nice'))

    // Move to Done.
    fireEvent.click(within(drawer).getByRole('button', { name: 'Done' }))
    await waitFor(() => expect(k.updateKanbanTask).toHaveBeenCalledWith('t1', { status: 'done' }))

    // Triage-only actions present; reclaim + archive work.
    fireEvent.click(within(drawer).getByText('Specify'))
    await waitFor(() => expect(k.specifyKanbanTask).toHaveBeenCalledWith('t1'))
    fireEvent.click(within(drawer).getByText('Reclaim'))
    await waitFor(() => expect(k.reclaimKanbanTask).toHaveBeenCalledWith('t1'))
    fireEvent.click(within(drawer).getByText('Archive'))
    await waitFor(() => expect(k.archiveKanbanTask).toHaveBeenCalledWith('t1'))
  })

  it('Workers tab lists active workers and terminates them', async () => {
    k.getKanbanWorkers.mockResolvedValue({
      workers: [{ profile: 'researcher', run_id: 'run99887', task_id: 'tX', worker_pid: 1234 }]
    })
    render(<KanbanView onClose={() => {}} />)
    fireEvent.click(await screen.findByRole('button', { name: 'workers' }))
    const panel = await screen.findByTestId('kanban-workers')
    await waitFor(() => expect(within(panel).getByText(/run99887/)).toBeTruthy())
    fireEvent.click(within(panel).getByText('Terminate'))
    await waitFor(() => expect(k.terminateKanbanRun).toHaveBeenCalledWith('run99887'))
  })

  it('Profiles tab renders profiles and the default assignee', async () => {
    k.getKanbanProfiles.mockResolvedValue({
      profiles: [{ description: 'web research', is_default: true, model: 'sonnet', name: 'researcher', provider: 'anthropic', skill_count: 3 }]
    })
    k.getKanbanOrchestration.mockResolvedValue({ resolved_default_assignee: 'researcher' })
    render(<KanbanView onClose={() => {}} />)
    fireEvent.click(await screen.findByRole('button', { name: 'profiles' }))
    const panel = await screen.findByTestId('kanban-profiles')
    // 'web research' (the description) is unique; 'researcher' shows as both the
    // default-assignee and the profile name, so assert via getAllByText.
    await waitFor(() => expect(within(panel).getByText('web research')).toBeTruthy())
    expect(within(panel).getAllByText('researcher').length).toBeGreaterThan(0)
    expect(within(panel).getByText('default')).toBeTruthy()
  })
})
