// @vitest-environment jsdom

import { type ToolCallMessagePartProps } from '@assistant-ui/react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { $clarifyRequests, setClarifyRequest } from '@/store/clarify'
import { $gateway } from '@/store/gateway'
import { $activeSessionId } from '@/store/session'

import { ClarifyTool } from './clarify-tool'

const questions = [
  { qid: 'q0', question: 'Which environment?', choices: ['Staging', 'Production'], multi_select: false },
  { qid: 'q1', question: 'Any notes?', choices: null, multi_select: false }
]

describe('ClarifyTool batch mode', () => {
  const request = vi.fn(async () => ({ ok: true }))

  beforeEach(() => {
    request.mockClear()
    $activeSessionId.set('session-1')
    $clarifyRequests.set({})
    $gateway.set({ request } as never)
    setClarifyRequest({
      requestId: 'request-1',
      question: 'Two questions',
      choices: null,
      questions: questions.map((item, index) => ({
        qid: item.qid,
        id: null,
        question: item.question,
        choices: item.choices,
        multiSelect: Boolean(index < 0)
      })),
      sessionId: 'session-1'
    })
  })

  afterEach(() => {
    $gateway.set(null)
    $clarifyRequests.set({})
    $activeSessionId.set(null)
  })

  it('collects several answers and submits one ordered batch payload', async () => {
    const props = {
      args: { questions },
      result: undefined
    } as unknown as ToolCallMessagePartProps

    render(ClarifyTool(props))

    expect(screen.getByText('2 questions')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /Production/ }))
    fireEvent.change(screen.getByPlaceholderText(/Type your answer/), { target: { value: 'Deploy after approval' } })
    fireEvent.click(screen.getByRole('button', { name: 'Submit answers' }))

    await waitFor(() => expect(request).toHaveBeenCalledOnce())
    const [method, params] = request.mock.calls[0] as unknown as [string, { answer: string; request_id: string }]
    expect(method).toBe('clarify.respond')
    expect(params.request_id).toBe('request-1')
    expect(JSON.parse(params.answer)).toEqual({
      answers: { q0: 'Production', q1: 'Deploy after approval' }
    })
  })
})
