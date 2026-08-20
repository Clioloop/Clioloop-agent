import { useCallback, useEffect, useMemo, useState } from 'react'

import { PageLoader } from '@/components/page-loader'
import { StatusDot } from '@/components/status-dot'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Codicon } from '@/components/ui/codicon'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'

export type GatewayRequest = <T>(method: string, params?: Record<string, unknown>, timeoutMs?: number) => Promise<T>

export interface BotRosterItem {
  display_name: string
  gateway_running: boolean
  handle: string
  key: string
  model: null | string
  profile: string
  provider: null | string
  source: string
  source_label: string
  title: string
}

interface BotDetail extends BotRosterItem {
  session_id: string
}

interface BotRoomMember {
  handle: string
  profile: string
  source: string
  source_label: string
}

interface BotRoomMessage {
  author: string
  content: string
  created_at: number
  epoch?: number
  id: string
  late?: boolean
  profile?: string
  round?: number
  seq: number
  source?: string
}

interface BotRoomActivity {
  elapsed_seconds?: number
  error?: string
  finished_at?: number
  id: string
  late?: boolean
  member: string
  round: number
  state: string
}

export interface BotRoom {
  active_epoch: number
  activity: BotRoomActivity[]
  created_at: number
  id: string
  members: BotRoomMember[]
  messages: BotRoomMessage[]
  name: string
  needs_user: boolean
  state: string
  updated_at: number
  visible_messages?: BotRoomMessage[]
}

interface BotTurnResult {
  activity: BotRoomActivity[]
  epoch: number
  messages: BotRoomMessage[]
  needs_user: boolean
  room_id: string
  rounds: number
  state: string
  suppressed: number
}

interface BotsViewProps {
  onOpenBotChat: (profile: string, sessionId: string, displayName: string) => void
  requestGateway: GatewayRequest
}

const LONG_RPC_TIMEOUT_MS = 11 * 60 * 1000
const ROOM_MAX_MEMBERS = 6
const ROOM_MIN_MEMBERS = 2

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

function roomStateLabel(state: string): string {
  return state.replace(/_/g, ' ')
}

function formatTime(value: number): string {
  if (!value) {
    return ''
  }

  return new Date(value * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export function BotsView({ onOpenBotChat, requestGateway }: BotsViewProps) {
  const [bots, setBots] = useState<BotRosterItem[] | null>(null)
  const [rooms, setRooms] = useState<BotRoom[] | null>(null)
  const [selectedBotProfile, setSelectedBotProfile] = useState<string | null>(null)
  const [selectedRoomId, setSelectedRoomId] = useState<string | null>(null)
  const [room, setRoom] = useState<BotRoom | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [openingBot, setOpeningBot] = useState(false)
  const [dmText, setDmText] = useState('')
  const [dmReply, setDmReply] = useState<string | null>(null)
  const [dmSending, setDmSending] = useState(false)
  const [creatingRoom, setCreatingRoom] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [roomName, setRoomName] = useState('')
  const [roomMembers, setRoomMembers] = useState<string[]>([])
  const [roomText, setRoomText] = useState('')
  const [roomSending, setRoomSending] = useState(false)
  const [deletingRoom, setDeletingRoom] = useState(false)
  const [lastTurn, setLastTurn] = useState<BotTurnResult | null>(null)

  const selectedBot = useMemo(
    () => bots?.find(bot => bot.profile === selectedBotProfile) ?? null,
    [bots, selectedBotProfile]
  )

  const refreshRoomList = useCallback(async () => {
    const response = await requestGateway<{ rooms: BotRoom[] }>('bot.rooms.list')
    setRooms(response.rooms)

    return response.rooms
  }, [requestGateway])

  const openRoom = useCallback(
    async (roomId: string) => {
      setSelectedRoomId(roomId)
      setLastTurn(null)
      setError(null)

      try {
        const response = await requestGateway<{ room: BotRoom }>('bot.rooms.get', { room_id: roomId })
        setRoom(response.room)
      } catch (nextError) {
        setRoom(null)
        setError(errorMessage(nextError))
      }
    },
    [requestGateway]
  )

  const refresh = useCallback(
    async (silent = false) => {
      if (!silent) {
        setRefreshing(true)
      }

      try {
        const [botResponse, nextRooms] = await Promise.all([
          requestGateway<{ bots: BotRosterItem[] }>('bot.list'),
          refreshRoomList()
        ])

        setBots(botResponse.bots)
        setSelectedBotProfile(current => current ?? botResponse.bots[0]?.profile ?? null)
        setSelectedRoomId(current => current ?? nextRooms[0]?.id ?? null)
        setError(null)
      } catch (nextError) {
        setError(errorMessage(nextError))
      } finally {
        if (!silent) {
          setRefreshing(false)
        }
      }
    },
    [refreshRoomList, requestGateway]
  )

  useEffect(() => {
    void refresh()
  }, [refresh])

  useEffect(() => {
    if (selectedRoomId) {
      void openRoom(selectedRoomId)
    } else {
      setRoom(null)
    }
  }, [openRoom, selectedRoomId])

  const handleOpenBotChat = async (bot: BotRosterItem) => {
    setOpeningBot(true)
    setError(null)

    try {
      const response = await requestGateway<{ bot: BotDetail }>('bot.get', { profile: bot.profile })
      onOpenBotChat(bot.profile, response.bot.session_id, bot.display_name)
    } catch (nextError) {
      setError(errorMessage(nextError))
    } finally {
      setOpeningBot(false)
    }
  }

  const handleSendDm = async () => {
    if (!selectedBot || !dmText.trim()) {
      return
    }

    setDmSending(true)
    setDmReply(null)
    setError(null)

    try {
      const response = await requestGateway<{ reply: string; session_id: string }>(
        'bot.dm',
        { message: dmText.trim(), profile: selectedBot.profile, sender: 'user' },
        LONG_RPC_TIMEOUT_MS
      )

      setDmText('')
      setDmReply(response.reply)
    } catch (nextError) {
      setError(errorMessage(nextError))
    } finally {
      setDmSending(false)
    }
  }

  const toggleRoomMember = (profile: string, checked: boolean) => {
    setRoomMembers(current => {
      if (checked) {
        return current.includes(profile) || current.length >= ROOM_MAX_MEMBERS ? current : [...current, profile]
      }

      return current.filter(item => item !== profile)
    })
  }

  const handleCreateRoom = async () => {
    const name = roomName.trim()

    if (!name || roomMembers.length < ROOM_MIN_MEMBERS || roomMembers.length > ROOM_MAX_MEMBERS) {
      return
    }

    setCreatingRoom(true)
    setError(null)

    try {
      const response = await requestGateway<{ room: BotRoom }>('bot.rooms.create', {
        members: roomMembers,
        name
      })

      setRoomName('')
      setRoomMembers([])
      setCreateOpen(false)
      await refreshRoomList()
      await openRoom(response.room.id)
    } catch (nextError) {
      setError(errorMessage(nextError))
    } finally {
      setCreatingRoom(false)
    }
  }

  const handleSendRoomMessage = async () => {
    if (!room || !roomText.trim()) {
      return
    }

    setRoomSending(true)
    setLastTurn(null)
    setError(null)

    try {
      const turn = await requestGateway<BotTurnResult>(
        'bot.rooms.send',
        { message: roomText.trim(), room_id: room.id },
        LONG_RPC_TIMEOUT_MS
      )

      setRoomText('')
      setLastTurn(turn)
      await Promise.all([openRoom(room.id), refreshRoomList()])
    } catch (nextError) {
      setError(errorMessage(nextError))
      await openRoom(room.id)
    } finally {
      setRoomSending(false)
    }
  }

  const handleDeleteRoom = async () => {
    if (!room || !window.confirm(`Delete Bot room “${room.name}”?`)) {
      return
    }

    setDeletingRoom(true)
    setError(null)

    try {
      await requestGateway('bot.rooms.delete', { room_id: room.id })
      const nextRooms = await refreshRoomList()
      const nextId = nextRooms[0]?.id ?? null
      setSelectedRoomId(nextId)
      setRoom(null)

      if (nextId) {
        await openRoom(nextId)
      }
    } catch (nextError) {
      setError(errorMessage(nextError))
    } finally {
      setDeletingRoom(false)
    }
  }

  if (bots === null || rooms === null) {
    return <PageLoader label="Loading Bots" />
  }

  return (
    <section className="flex h-full min-h-0 flex-col bg-(--ui-chat-surface-background) pt-(--titlebar-height)">
      <header className="flex shrink-0 items-center justify-between border-b border-(--ui-stroke-secondary) px-6 py-3">
        <div>
          <h1 className="text-sm font-semibold">Bots</h1>
          <p className="text-xs text-(--ui-text-tertiary)">Profile-backed teammates and bounded collaboration rooms.</p>
        </div>
        <Button disabled={refreshing} onClick={() => void refresh()} size="sm" variant="ghost">
          <Codicon name="refresh" spinning={refreshing} />
          Refresh
        </Button>
      </header>

      {error ? (
        <Alert className="mx-6 mt-3 w-auto" variant="destructive">
          <Codicon name="error" />
          <AlertTitle>Bot Mode error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      <div className="grid min-h-0 flex-1 grid-cols-[minmax(15rem,19rem)_minmax(0,1fr)] max-[56rem]:grid-cols-1">
        <aside className="min-h-0 overflow-y-auto border-r border-(--ui-stroke-secondary) p-3 max-[56rem]:max-h-72 max-[56rem]:border-b max-[56rem]:border-r-0">
          <div className="mb-2 flex items-center justify-between px-1">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-(--ui-text-tertiary)">Roster</h2>
            <Badge variant="muted">{bots.length}</Badge>
          </div>
          <div className="grid gap-1.5">
            {bots.map(bot => (
              <button
                aria-pressed={selectedBotProfile === bot.profile}
                className={cn(
                  'grid w-full grid-cols-[auto_minmax(0,1fr)] gap-x-2 rounded-md border border-transparent px-2.5 py-2 text-left hover:bg-(--ui-control-hover-background)',
                  selectedBotProfile === bot.profile &&
                    'border-(--ui-stroke-tertiary) bg-(--ui-control-active-background)'
                )}
                key={bot.key}
                onClick={() => {
                  setSelectedBotProfile(bot.profile)
                  setDmReply(null)
                }}
                type="button"
              >
                <span className="mt-1 grid size-7 place-items-center rounded bg-primary/10 text-primary">
                  <Codicon name="hubot" />
                </span>
                <span className="min-w-0">
                  <span className="flex items-center gap-1.5">
                    <strong className="truncate text-xs font-semibold">{bot.display_name}</strong>
                    <StatusDot tone={bot.gateway_running ? 'good' : 'muted'} />
                  </span>
                  <span className="block truncate text-[0.6875rem] text-(--ui-text-tertiary)">
                    {bot.title || 'Clio Bot'}
                  </span>
                  <span className="mt-1 flex flex-wrap gap-1">
                    <Badge variant="outline">{bot.profile}</Badge>
                    <Badge variant="muted">{bot.model || 'default model'}</Badge>
                  </span>
                  <span className="mt-1 block text-[0.65rem] text-(--ui-text-quaternary)">
                    {bot.gateway_running ? 'Gateway running' : 'Gateway stopped'}
                    {bot.provider ? ` · ${bot.provider}` : ''}
                  </span>
                </span>
              </button>
            ))}
          </div>
        </aside>

        <main className="min-h-0 overflow-y-auto p-5">
          <div className="mx-auto grid max-w-5xl gap-6">
            {selectedBot ? (
              <section aria-labelledby="bot-direct-title" className="rounded-lg border border-(--ui-stroke-secondary) bg-card p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h2 className="text-sm font-semibold" id="bot-direct-title">
                      {selectedBot.display_name}
                    </h2>
                    <p className="text-xs text-(--ui-text-tertiary)">
                      @{selectedBot.handle} · {selectedBot.profile} · {selectedBot.model || 'default model'}
                    </p>
                  </div>
                  <Button
                    disabled={openingBot}
                    onClick={() => void handleOpenBotChat(selectedBot)}
                    size="sm"
                    variant="outline"
                  >
                    <Codicon name="comment-discussion" />
                    Open Bot Chat
                  </Button>
                </div>
                <div className="mt-4 grid gap-2">
                  <Textarea
                    aria-label={`Direct message ${selectedBot.display_name}`}
                    disabled={dmSending}
                    maxLength={200_000}
                    onChange={event => setDmText(event.target.value)}
                    placeholder={`Send a local DM to ${selectedBot.display_name}…`}
                    value={dmText}
                  />
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[0.6875rem] text-(--ui-text-quaternary)">
                      Delivered to this Bot’s canonical chat with user attribution.
                    </span>
                    <Button disabled={dmSending || !dmText.trim()} onClick={() => void handleSendDm()} size="sm">
                      <Codicon name={dmSending ? 'loading' : 'send'} spinning={dmSending} />
                      {dmSending ? 'Waiting for Bot…' : 'Send DM'}
                    </Button>
                  </div>
                  {dmReply !== null ? (
                    <div className="mt-2 rounded-md border border-(--ui-stroke-secondary) bg-background p-3">
                      <div className="mb-1 text-[0.6875rem] font-semibold text-primary">{selectedBot.display_name}</div>
                      <div className="whitespace-pre-wrap text-xs leading-relaxed">{dmReply || '(No visible reply)'}</div>
                    </div>
                  ) : null}
                </div>
              </section>
            ) : (
              <div className="rounded-lg border border-dashed p-6 text-center text-xs text-(--ui-text-tertiary)">
                No Bot-enabled profiles are available.
              </div>
            )}

            <section aria-labelledby="rooms-title" className="grid gap-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h2 className="text-sm font-semibold" id="rooms-title">
                    Bot rooms
                  </h2>
                  <p className="text-[0.6875rem] text-(--ui-text-tertiary)">
                    2–6 Bots · serial turns · up to 3 rounds · at most 10 visible Bot replies per send.
                  </p>
                </div>
                <Button onClick={() => setCreateOpen(current => !current)} size="sm" variant="outline">
                  <Codicon name={createOpen ? 'close' : 'add'} />
                  {createOpen ? 'Cancel' : 'New room'}
                </Button>
              </div>

              {createOpen ? (
                <div className="grid gap-3 rounded-lg border border-(--ui-stroke-secondary) bg-card p-4">
                  <Input
                    aria-label="Room name"
                    maxLength={80}
                    onChange={event => setRoomName(event.target.value)}
                    placeholder="Room name"
                    value={roomName}
                  />
                  <fieldset>
                    <legend className="mb-2 text-xs font-medium">Members ({roomMembers.length}/6)</legend>
                    <div className="grid grid-cols-2 gap-2 max-[46rem]:grid-cols-1">
                      {bots.map(bot => {
                        const checked = roomMembers.includes(bot.profile)
                        const capped = !checked && roomMembers.length >= ROOM_MAX_MEMBERS

                        return (
                          <label
                            className={cn(
                              'flex items-center gap-2 rounded border border-(--ui-stroke-secondary) px-2.5 py-2 text-xs',
                              capped && 'opacity-50'
                            )}
                            key={bot.key}
                          >
                            <Checkbox
                              aria-label={`Include ${bot.display_name}`}
                              checked={checked}
                              disabled={capped}
                              onCheckedChange={value => toggleRoomMember(bot.profile, value === true)}
                            />
                            <span className="min-w-0 flex-1 truncate">{bot.display_name}</span>
                            <span className="text-(--ui-text-quaternary)">@{bot.handle}</span>
                          </label>
                        )
                      })}
                    </div>
                  </fieldset>
                  {roomMembers.length > 0 && roomMembers.length < ROOM_MIN_MEMBERS ? (
                    <p className="text-[0.6875rem] text-amber-600 dark:text-amber-300">Select at least 2 distinct Bots.</p>
                  ) : null}
                  <Button
                    className="justify-self-end"
                    disabled={creatingRoom || !roomName.trim() || roomMembers.length < ROOM_MIN_MEMBERS}
                    onClick={() => void handleCreateRoom()}
                    size="sm"
                  >
                    <Codicon name={creatingRoom ? 'loading' : 'organization'} spinning={creatingRoom} />
                    Create bounded room
                  </Button>
                </div>
              ) : null}

              <div className="grid min-h-96 grid-cols-[14rem_minmax(0,1fr)] overflow-hidden rounded-lg border border-(--ui-stroke-secondary) bg-card max-[48rem]:grid-cols-1">
                <nav aria-label="Bot rooms" className="border-r border-(--ui-stroke-secondary) p-2 max-[48rem]:border-b max-[48rem]:border-r-0">
                  {rooms.length ? (
                    <div className="grid gap-1">
                      {rooms.map(item => (
                        <button
                          aria-current={selectedRoomId === item.id ? 'page' : undefined}
                          className={cn(
                            'rounded px-2.5 py-2 text-left hover:bg-(--ui-control-hover-background)',
                            selectedRoomId === item.id && 'bg-(--ui-control-active-background)'
                          )}
                          key={item.id}
                          onClick={() => void openRoom(item.id)}
                          type="button"
                        >
                          <span className="block truncate text-xs font-medium">{item.name}</span>
                          <span className="mt-0.5 flex items-center gap-1 text-[0.65rem] text-(--ui-text-tertiary)">
                            <StatusDot tone={item.needs_user ? 'warn' : item.state === 'running' ? 'good' : 'muted'} />
                            {item.members.length} Bots · {roomStateLabel(item.state)}
                          </span>
                        </button>
                      ))}
                    </div>
                  ) : (
                    <div className="p-3 text-center text-xs text-(--ui-text-tertiary)">No rooms yet.</div>
                  )}
                </nav>

                {room ? (
                  <div className="flex min-h-0 flex-col">
                    <header className="flex flex-wrap items-start justify-between gap-2 border-b border-(--ui-stroke-secondary) px-4 py-3">
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="text-xs font-semibold">{room.name}</h3>
                          <Badge variant={room.needs_user ? 'warn' : 'muted'}>{roomStateLabel(room.state)}</Badge>
                        </div>
                        <p className="mt-1 text-[0.6875rem] text-(--ui-text-tertiary)">
                          {room.members.map(member => `@${member.handle}`).join(', ')}
                        </p>
                      </div>
                      <Button
                        aria-label={`Delete ${room.name}`}
                        disabled={deletingRoom || roomSending}
                        onClick={() => void handleDeleteRoom()}
                        size="icon-xs"
                        variant="ghost"
                      >
                        <Codicon name={deletingRoom ? 'loading' : 'trash'} spinning={deletingRoom} />
                      </Button>
                    </header>

                    {room.needs_user ? (
                      <Alert className="m-3 mb-0 w-auto" variant="warning">
                        <Codicon name="person" />
                        <AlertTitle>Your judgment is needed</AlertTitle>
                        <AlertDescription>A Bot mentioned @user. Reply below to continue the room.</AlertDescription>
                      </Alert>
                    ) : null}

                    <div aria-label="Room transcript" className="min-h-52 flex-1 space-y-3 overflow-y-auto p-4">
                      {room.messages.length ? (
                        room.messages.map(message => {
                          const authorBot = bots.find(bot => bot.profile === message.profile)
                          const authorName = message.author === 'user' ? 'You' : authorBot?.display_name || `@${message.author}`

                          return (
                            <article
                              className={cn(
                                'max-w-[85%] rounded-md border border-(--ui-stroke-secondary) px-3 py-2',
                                message.author === 'user' ? 'ml-auto bg-primary/5' : 'bg-background'
                              )}
                              data-author={message.author}
                              key={message.id}
                            >
                              <div className="mb-1 flex flex-wrap items-center gap-1.5 text-[0.65rem]">
                                <strong className={message.author === 'user' ? 'text-foreground' : 'text-primary'}>{authorName}</strong>
                                {message.author !== 'user' ? <span className="text-(--ui-text-quaternary)">@{message.author}</span> : null}
                                {message.round ? <Badge variant="outline">round {message.round}</Badge> : null}
                                {message.late ? <Badge variant="warn">slow</Badge> : null}
                                <time className="ml-auto text-(--ui-text-quaternary)">{formatTime(message.created_at)}</time>
                              </div>
                              <div className="whitespace-pre-wrap text-xs leading-relaxed">{message.content}</div>
                            </article>
                          )
                        })
                      ) : (
                        <div className="grid min-h-40 place-items-center text-center text-xs text-(--ui-text-tertiary)">
                          Send a message to start a bounded deliberation.
                        </div>
                      )}
                    </div>

                    <div className="border-t border-(--ui-stroke-secondary) p-3">
                      <Textarea
                        aria-label={`Message ${room.name}`}
                        disabled={roomSending}
                        maxLength={100_000}
                        onChange={event => setRoomText(event.target.value)}
                        placeholder="Message the room. Mention @handle to target a Bot…"
                        value={roomText}
                      />
                      <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                        <span className="text-[0.65rem] text-(--ui-text-quaternary)">
                          {roomSending
                            ? 'Running serial Bot turns within the room limits…'
                            : 'No mention selects the whole room. New input supersedes stale work.'}
                        </span>
                        <Button
                          disabled={roomSending || !roomText.trim()}
                          onClick={() => void handleSendRoomMessage()}
                          size="sm"
                        >
                          <Codicon name={roomSending ? 'loading' : 'send'} spinning={roomSending} />
                          {roomSending ? 'Bots working…' : 'Send to room'}
                        </Button>
                      </div>
                      {lastTurn ? (
                        <p className="mt-2 text-[0.6875rem] text-(--ui-text-tertiary)">
                          Turn {lastTurn.epoch}: {lastTurn.rounds} round{lastTurn.rounds === 1 ? '' : 's'}, {lastTurn.suppressed}{' '}
                          hidden pass/duplicate/failure{lastTurn.suppressed === 1 ? '' : 's'}.
                        </p>
                      ) : null}
                    </div>

                    {room.activity.length ? (
                      <details className="border-t border-(--ui-stroke-secondary) px-4 py-2 text-[0.6875rem]">
                        <summary className="cursor-pointer text-(--ui-text-tertiary)">Private activity ({room.activity.length})</summary>
                        <div className="mt-2 grid max-h-40 gap-1 overflow-y-auto">
                          {room.activity.slice(-30).map(activity => (
                            <div
                              className={cn(
                                'flex flex-wrap items-center gap-2 rounded bg-background px-2 py-1',
                                (activity.state === 'failed' || activity.state === 'timeout') && 'text-destructive'
                              )}
                              key={activity.id}
                            >
                              <span className="font-medium">@{activity.member}</span>
                              <span>round {activity.round}</span>
                              <Badge
                                variant={activity.state === 'failed' || activity.state === 'timeout' ? 'destructive' : 'muted'}
                              >
                                {activity.state}
                              </Badge>
                              {typeof activity.elapsed_seconds === 'number' ? (
                                <span>{activity.elapsed_seconds.toFixed(1)}s</span>
                              ) : null}
                              {activity.error ? <span className="basis-full whitespace-pre-wrap">{activity.error}</span> : null}
                            </div>
                          ))}
                        </div>
                      </details>
                    ) : null}
                  </div>
                ) : (
                  <div className="grid min-h-80 place-items-center text-xs text-(--ui-text-tertiary)">
                    Select or create a Bot room.
                  </div>
                )}
              </div>
            </section>
          </div>
        </main>
      </div>
    </section>
  )
}
