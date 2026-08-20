// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { type BotRoom, type BotRosterItem, BotsView, type GatewayRequest } from './index'

const bots: BotRosterItem[] = [
  {
    display_name: 'Researcher',
    gateway_running: true,
    handle: 'researcher',
    key: 'local:researcher',
    model: 'gpt-5.6',
    profile: 'researcher',
    provider: 'managed',
    source: 'local',
    source_label: 'This device',
    title: 'Primary researcher'
  },
  {
    display_name: 'Reviewer',
    gateway_running: false,
    handle: 'reviewer',
    key: 'local:reviewer',
    model: 'claude-sonnet',
    profile: 'reviewer',
    provider: 'anthropic',
    source: 'local',
    source_label: 'This device',
    title: 'Quality reviewer'
  }
]

function makeRoom(overrides: Partial<BotRoom> = {}): BotRoom {
  return {
    active_epoch: 2,
    activity: [
      {
        elapsed_seconds: 1.2,
        error: 'Model unavailable',
        finished_at: 10,
        id: 'act-1',
        late: false,
        member: 'reviewer',
        round: 1,
        state: 'failed'
      }
    ],
    created_at: 1,
    id: 'room-1',
    members: [
      { handle: 'researcher', profile: 'researcher', source: 'local', source_label: 'This device' },
      { handle: 'reviewer', profile: 'reviewer', source: 'local', source_label: 'This device' }
    ],
    messages: [
      { author: 'user', content: 'Review the launch', created_at: 2, id: 'm1', seq: 1 },
      {
        author: 'researcher',
        content: 'I found a blocker. @user should choose.',
        created_at: 3,
        id: 'm2',
        profile: 'researcher',
        round: 1,
        seq: 2,
        source: 'local'
      }
    ],
    name: 'Launch review',
    needs_user: true,
    state: 'needs_user',
    updated_at: 3,
    ...overrides
  }
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('BotsView', () => {
  it('renders the authoritative roster and opens the canonical Bot Chat', async () => {
    const onOpenBotChat = vi.fn()

    const rpc = vi.fn(async (method: string, _params?: Record<string, unknown>, _timeoutMs?: number) => {
      if (method === 'bot.list') {
        return { bots }
      }

      if (method === 'bot.rooms.list') {
        return { rooms: [] }
      }

      if (method === 'bot.get') {
        return { bot: { ...bots[0], session_id: 'canonical-research' } }
      }

      throw new Error(`Unexpected RPC: ${method}`)
    })

    const requestGateway: GatewayRequest = async <T,>(
      method: string,
      params?: Record<string, unknown>,
      timeoutMs?: number
    ): Promise<T> => (await rpc(method, params, timeoutMs)) as T

    render(<BotsView onOpenBotChat={onOpenBotChat} requestGateway={requestGateway} />)

    expect(await screen.findByText('Primary researcher')).toBeTruthy()
    expect(screen.getByText('gpt-5.6')).toBeTruthy()
    expect(screen.getByText(/Gateway running/)).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: /open bot chat/i }))

    await waitFor(() =>
      expect(onOpenBotChat).toHaveBeenCalledWith('researcher', 'canonical-research', 'Researcher')
    )
    expect(rpc).toHaveBeenCalledWith('bot.get', { profile: 'researcher' }, undefined)
  })

  it('sends local DMs and renders attributed bounded-room state from RPC refreshes', async () => {
    let currentRoom = makeRoom()

    const rpc = vi.fn(async (method: string, params?: Record<string, unknown>, _timeoutMs?: number) => {
      if (method === 'bot.list') {
        return { bots }
      }

      if (method === 'bot.rooms.list') {
        return { rooms: [currentRoom] }
      }

      if (method === 'bot.rooms.get') {
        return { room: currentRoom }
      }

      if (method === 'bot.dm') {
        return { profile: 'researcher', reply: 'DM reply', session_id: 'canonical-research' }
      }

      if (method === 'bot.rooms.send') {
        currentRoom = makeRoom({
          activity: [],
          messages: [
            ...currentRoom.messages,
            { author: 'user', content: String(params?.message), created_at: 4, id: 'm3', seq: 3 },
            {
              author: 'reviewer',
              content: 'Ship after the fix.',
              created_at: 5,
              id: 'm4',
              profile: 'reviewer',
              round: 1,
              seq: 4,
              source: 'local'
            }
          ],
          needs_user: false,
          state: 'settled'
        })

        return {
          activity: [],
          epoch: 3,
          messages: currentRoom.messages.slice(-2),
          needs_user: false,
          room_id: currentRoom.id,
          rounds: 1,
          state: 'settled',
          suppressed: 0
        }
      }

      throw new Error(`Unexpected RPC: ${method}`)
    })

    const requestGateway: GatewayRequest = async <T,>(
      method: string,
      params?: Record<string, unknown>,
      timeoutMs?: number
    ): Promise<T> => (await rpc(method, params, timeoutMs)) as T

    render(<BotsView onOpenBotChat={vi.fn()} requestGateway={requestGateway} />)

    expect(await screen.findByText('Launch review')).toBeTruthy()
    expect(await screen.findByText('I found a blocker. @user should choose.')).toBeTruthy()
    expect(screen.getByText('Your judgment is needed')).toBeTruthy()

    fireEvent.change(screen.getByLabelText('Direct message Researcher'), { target: { value: 'Investigate this' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send DM' }))

    expect(await screen.findByText('DM reply')).toBeTruthy()
    expect(rpc).toHaveBeenCalledWith(
      'bot.dm',
      { message: 'Investigate this', profile: 'researcher', sender: 'user' },
      660_000
    )

    fireEvent.change(screen.getByLabelText('Message Launch review'), { target: { value: 'Can we ship?' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send to room' }))

    expect(await screen.findByText('Ship after the fix.')).toBeTruthy()
    expect(screen.getAllByText('Reviewer').length).toBeGreaterThan(1)
    expect(rpc).toHaveBeenCalledWith(
      'bot.rooms.send',
      { message: 'Can we ship?', room_id: 'room-1' },
      660_000
    )
  })
})
