// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { KanbanBoard } from '@/lib/clio-kanban'

import { KanbanView } from './index'

const { createKanbanTask, getKanbanBoard, updateKanbanTask } = vi.hoisted(() => ({
  createKanbanTask: vi.fn(),
  getKanbanBoard: vi.fn(),
  updateKanbanTask: vi.fn()
}))

vi.mock('@/lib/clio-kanban', () => ({
  createKanbanTask,
  getKanbanBoard,
  updateKanbanTask
}))

function board(): KanbanBoard {
  return {
    assignees: ['alice'],
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

describe('KanbanView', () => {
  beforeEach(() => {
    getKanbanBoard.mockResolvedValue(board())
    createKanbanTask.mockResolvedValue({ task: { id: 't3', priority: 0, status: 'triage', title: 'New' } })
    updateKanbanTask.mockResolvedValue({ task: { id: 't1', priority: 0, status: 'done', title: 'Triage me' } })
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('renders columns and cards from the board API', async () => {
    render(<KanbanView onClose={() => {}} />)
    expect(await screen.findByText('Triage me')).toBeTruthy()
    expect(screen.getByText('Ready task')).toBeTruthy()
    // Column headers (Triage / Ready / Done) are present.
    expect(screen.getByText('Triage')).toBeTruthy()
    expect(screen.getByText('Ready')).toBeTruthy()
    // Assignee surfaces on the ready card.
    expect(screen.getByText('alice')).toBeTruthy()
  })

  it('creates a bare task (no triage flag → backend parks it in triage)', async () => {
    render(<KanbanView onClose={() => {}} />)
    await screen.findByText('Triage me')

    const input = screen.getByLabelText('New task title') as HTMLInputElement
    fireEvent.change(input, { target: { value: 'Investigate flake' } })
    fireEvent.click(screen.getByText('Add task'))

    await waitFor(() => expect(createKanbanTask).toHaveBeenCalledWith({ title: 'Investigate flake' }))
  })

  it('opens a task drawer and moves a task via the API', async () => {
    render(<KanbanView onClose={() => {}} />)
    fireEvent.click(await screen.findByText('Triage me'))

    // Drawer shows; click "Done" move target.
    const drawer = await screen.findByTestId('kanban-drawer')
    expect(drawer).toBeTruthy()
    const doneButton = within(drawer).getByRole('button', { name: 'Done' })
    fireEvent.click(doneButton)

    await waitFor(() => expect(updateKanbanTask).toHaveBeenCalledWith('t1', { status: 'done' }))
  })
})
