import { type DragEvent as ReactDragEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { CLIO_PATHS_MIME, type DroppedFile, extractDroppedFiles } from '@/app/chat/hooks/use-composer-actions'
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
  identity_id?: string
  key: string
  model: null | string
  profile: string
  provider: null | string
  source: string
  source_label: string
  title: string
  worker_active?: boolean
  worker_session?: null | { id: string; last_active: number; source: string; title: string }
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
  pending_user_action?: null | {
    choices: string[]
    command?: string
    description?: string
    epoch: number
    kind: 'approval' | 'clarify'
    member: string
    profile: string
    question?: string
    request_id: string
    room_id: string
    session_id: string
  }
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
  onOpenBotChat: (profile: string, sessionId: string, displayName: string) => Promise<void> | void
  requestGateway: GatewayRequest
}

const LONG_RPC_TIMEOUT_MS = 11 * 60 * 1000
const ROOM_MAX_ATTACHMENTS = 12
const ROOM_MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024
const ROOM_REMOTE_ATTACHMENT_BYTES = 7 * 1024 * 1024
const ROOM_MAX_MEMBERS = 6
const ROOM_MIN_MEMBERS = 2

const ROOM_ATTACHMENT_MIME_BY_EXTENSION: Readonly<Record<string, string>> = {
  '.avif': 'image/avif',
  '.bmp': 'image/bmp',
  '.gif': 'image/gif',
  '.heic': 'image/heic',
  '.heif': 'image/heif',
  '.ico': 'image/x-icon',
  '.jpeg': 'image/jpeg',
  '.jpg': 'image/jpeg',
  '.markdown': 'text/markdown',
  '.md': 'text/markdown',
  '.pdf': 'application/pdf',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.text': 'text/plain',
  '.tif': 'image/tiff',
  '.tiff': 'image/tiff',
  '.txt': 'text/plain',
  '.webp': 'image/webp'
}

const ROOM_ATTACHMENT_PICKER_EXTENSIONS = Object.keys(ROOM_ATTACHMENT_MIME_BY_EXTENSION).map(extension =>
  extension.slice(1)
)

interface RoomAttachment {
  mime_type: string
  name: string
  path: string
  size: number
}

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

function fileNameFromPath(path: string): string {
  return path.split(/[\\/]/).filter(Boolean).pop() || path
}

function roomAttachmentMimeType(path: string): string | null {
  const name = fileNameFromPath(path)
  const dot = name.lastIndexOf('.')
  const extension = dot >= 0 ? name.slice(dot).toLowerCase() : ''

  return ROOM_ATTACHMENT_MIME_BY_EXTENSION[extension] ?? null
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`
  }

  const kibibytes = bytes / 1024

  if (kibibytes < 1024) {
    return `${Number(kibibytes.toFixed(kibibytes < 10 ? 1 : 0))} KiB`
  }

  const mebibytes = kibibytes / 1024

  return `${Number(mebibytes.toFixed(mebibytes < 10 ? 1 : 0))} MiB`
}

async function inspectRoomAttachment(candidate: DroppedFile): Promise<RoomAttachment> {
  const path = candidate.path.trim()

  if (!path) {
    throw new Error('Could not resolve a real filesystem path for the dropped file.')
  }

  const mimeType = roomAttachmentMimeType(path)

  if (!mimeType) {
    throw new Error(`${fileNameFromPath(path)} is not a supported PDF, image, text, or Markdown file.`)
  }

  const inspectFile = window.clioDesktop?.readFileText

  if (!inspectFile) {
    throw new Error('Desktop file inspection is unavailable.')
  }

  const metadata = await inspectFile(path)
  const resolvedPath = metadata.path || path
  const name = fileNameFromPath(resolvedPath)
  const size = typeof metadata.byteSize === 'number' ? metadata.byteSize : candidate.file?.size

  if (!name || name.length > 200) {
    throw new Error('Attachment names must be plain filenames of at most 200 characters.')
  }

  if (typeof size !== 'number' || !Number.isFinite(size) || size < 0) {
    throw new Error(`Could not determine the size of ${name}.`)
  }

  if (size > ROOM_MAX_ATTACHMENT_BYTES) {
    throw new Error(`${name} exceeds the 25 MiB local attachment limit.`)
  }

  return { mime_type: mimeType, name, path: resolvedPath, size }
}

function dragHasRoomFiles(event: ReactDragEvent): boolean {
  return Array.from(event.dataTransfer.types || []).some(type => type === 'Files' || type === CLIO_PATHS_MIME)
}

export function BotsView({ onOpenBotChat, requestGateway }: BotsViewProps) {
  const [bots, setBots] = useState<BotRosterItem[] | null>(null)
  const [rooms, setRooms] = useState<BotRoom[] | null>(null)
  const [selectedBotIdentity, setSelectedBotIdentity] = useState<string | null>(null)
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
  const [roomAttachments, setRoomAttachments] = useState<RoomAttachment[]>([])
  const [roomAttachmentIssue, setRoomAttachmentIssue] = useState<string | null>(null)
  const [roomAttachmentDragActive, setRoomAttachmentDragActive] = useState(false)
  const [roomPickingAttachments, setRoomPickingAttachments] = useState(false)
  const [roomSending, setRoomSending] = useState(false)
  const [roomResponding, setRoomResponding] = useState(false)
  const [handoffText, setHandoffText] = useState('')
  const [deletingRoom, setDeletingRoom] = useState(false)
  const [lastTurn, setLastTurn] = useState<BotTurnResult | null>(null)
  const activeRoomIdRef = useRef<string | null>(null)
  const roomAttachmentsRef = useRef<RoomAttachment[]>([])
  const roomDragDepthRef = useRef(0)

  const selectedBot = useMemo(
    () => bots?.find(bot => (bot.identity_id || bot.key) === selectedBotIdentity) ?? null,
    [bots, selectedBotIdentity]
  )

  const roomHasRemoteMembers = useMemo(() => room?.members.some(member => member.source !== 'local') ?? false, [room])

  const remoteOversizeAttachments = useMemo(
    () => (roomHasRemoteMembers ? roomAttachments.filter(item => item.size > ROOM_REMOTE_ATTACHMENT_BYTES) : []),
    [roomAttachments, roomHasRemoteMembers]
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
        setSelectedBotIdentity(
          current => current ?? botResponse.bots[0]?.identity_id ?? botResponse.bots[0]?.key ?? null
        )
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

  useEffect(() => {
    activeRoomIdRef.current = selectedRoomId
    roomAttachmentsRef.current = []
    roomDragDepthRef.current = 0
    setRoomAttachments([])
    setRoomAttachmentIssue(null)
    setRoomAttachmentDragActive(false)
  }, [selectedRoomId])

  useEffect(() => {
    if (!roomSending || !selectedRoomId) {
      return
    }

    const roomId = selectedRoomId

    const timer = window.setInterval(() => {
      void requestGateway<{ room: BotRoom }>('bot.rooms.get', { room_id: roomId })
        .then(response => {
          if (activeRoomIdRef.current === roomId) {
            setRoom(response.room)
          }
        })
        .catch(() => undefined)
    }, 300)

    return () => window.clearInterval(timer)
  }, [requestGateway, roomSending, selectedRoomId])

  const handleOpenBotChat = async (bot: BotRosterItem) => {
    setOpeningBot(true)
    setError(null)

    try {
      const response = await requestGateway<{ bot: BotDetail }>('bot.get', { profile: bot.profile })
      await onOpenBotChat(bot.profile, response.bot.session_id, bot.display_name)
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

  const addRoomAttachments = useCallback(async (candidates: DroppedFile[]) => {
    const targetRoomId = activeRoomIdRef.current

    if (!targetRoomId || candidates.length === 0) {
      return
    }

    setRoomAttachmentIssue(null)
    const inspectable = candidates.filter(candidate => !candidate.isDirectory)
    const issues = candidates.length > inspectable.length ? ['Folders cannot be attached to Bot rooms.'] : []
    const inspected = await Promise.allSettled(inspectable.map(candidate => inspectRoomAttachment(candidate)))

    if (activeRoomIdRef.current !== targetRoomId) {
      return
    }

    const current = roomAttachmentsRef.current
    const next = [...current]
    const seenPaths = new Set(current.map(item => item.path))
    let hitLimit = false

    for (const result of inspected) {
      if (result.status === 'rejected') {
        issues.push(errorMessage(result.reason))

        continue
      }

      if (seenPaths.has(result.value.path)) {
        continue
      }

      if (next.length >= ROOM_MAX_ATTACHMENTS) {
        hitLimit = true

        continue
      }

      seenPaths.add(result.value.path)
      next.push(result.value)
    }

    if (hitLimit) {
      issues.push(`At most ${ROOM_MAX_ATTACHMENTS} attachments can be sent to a room.`)
    }

    roomAttachmentsRef.current = next
    setRoomAttachments(next)
    setRoomAttachmentIssue(
      issues.length > 1 ? `${issues[0]} (+${issues.length - 1} more)` : issues.length === 1 ? issues[0] : null
    )
  }, [])

  const clearRoomAttachments = useCallback(() => {
    roomAttachmentsRef.current = []
    setRoomAttachments([])
    setRoomAttachmentIssue(null)
  }, [])

  const removeRoomAttachment = useCallback((path: string) => {
    const next = roomAttachmentsRef.current.filter(item => item.path !== path)

    roomAttachmentsRef.current = next
    setRoomAttachments(next)
    setRoomAttachmentIssue(null)
  }, [])

  const handlePickRoomAttachments = async () => {
    const selectPaths = window.clioDesktop?.selectPaths

    if (!selectPaths) {
      setRoomAttachmentIssue('Desktop file picker is unavailable.')

      return
    }

    setRoomPickingAttachments(true)
    setRoomAttachmentIssue(null)

    try {
      const paths = await selectPaths({
        filters: [
          { extensions: ROOM_ATTACHMENT_PICKER_EXTENSIONS, name: 'Supported attachments' },
          { extensions: ['pdf'], name: 'PDF documents' },
          {
            extensions: [
              'avif',
              'bmp',
              'gif',
              'heic',
              'heif',
              'ico',
              'jpeg',
              'jpg',
              'png',
              'svg',
              'tif',
              'tiff',
              'webp'
            ],
            name: 'Images'
          },
          { extensions: ['txt', 'text', 'md', 'markdown'], name: 'Text and Markdown' }
        ],
        multiple: true,
        title: 'Attach files to Bot room'
      })

      await addRoomAttachments((paths || []).map(path => ({ path })))
    } catch (nextError) {
      setRoomAttachmentIssue(errorMessage(nextError))
    } finally {
      setRoomPickingAttachments(false)
    }
  }

  const handleRoomAttachmentDragEnter = (event: ReactDragEvent<HTMLDivElement>) => {
    if (roomSending || !dragHasRoomFiles(event)) {
      return
    }

    event.preventDefault()
    roomDragDepthRef.current += 1
    setRoomAttachmentDragActive(true)
  }

  const handleRoomAttachmentDragLeave = () => {
    roomDragDepthRef.current -= 1

    if (roomDragDepthRef.current <= 0) {
      roomDragDepthRef.current = 0
      setRoomAttachmentDragActive(false)
    }
  }

  const handleRoomAttachmentDragOver = (event: ReactDragEvent<HTMLDivElement>) => {
    if (roomSending || !dragHasRoomFiles(event)) {
      return
    }

    event.preventDefault()
    event.dataTransfer.dropEffect = 'copy'
  }

  const handleRoomAttachmentDrop = (event: ReactDragEvent<HTMLDivElement>) => {
    if (roomSending || !dragHasRoomFiles(event)) {
      return
    }

    event.preventDefault()
    event.stopPropagation()
    roomDragDepthRef.current = 0
    setRoomAttachmentDragActive(false)
    const candidates = extractDroppedFiles(event.dataTransfer)

    if (candidates.length === 0) {
      setRoomAttachmentIssue('Could not resolve a real filesystem path for the dropped file.')

      return
    }

    void addRoomAttachments(candidates)
  }

  const handleSendRoomMessage = async () => {
    const message = roomText.trim()

    if (!room || !message || remoteOversizeAttachments.length > 0) {
      return
    }

    const attachments = roomAttachments.map(item => ({ ...item }))

    setRoomSending(true)
    setLastTurn(null)
    setError(null)

    try {
      const turn = await requestGateway<BotTurnResult>(
        'bot.rooms.send',
        {
          ...(attachments.length > 0 ? { attachments } : {}),
          message,
          room_id: room.id
        },
        LONG_RPC_TIMEOUT_MS
      )

      setRoomText('')
      clearRoomAttachments()
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

  const handleRoomUserAction = async (response: string) => {
    const action = room?.pending_user_action
    const answer = response.trim()

    if (!room || !action || !answer) {
      return
    }

    setRoomResponding(true)
    setError(null)

    try {
      await requestGateway('bot.rooms.respond', {
        epoch: action.epoch,
        request_id: action.request_id,
        response: answer,
        room_id: room.id,
        session_id: action.session_id
      })
      setHandoffText('')
      await openRoom(room.id)
    } catch (nextError) {
      setError(errorMessage(nextError))
    } finally {
      setRoomResponding(false)
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
            {bots.map(bot => {
              const identity = bot.identity_id || bot.key

              return (
                <button
                  aria-pressed={selectedBotIdentity === identity}
                  className={cn(
                    'grid w-full grid-cols-[auto_minmax(0,1fr)] gap-x-2 rounded-md border border-transparent px-2.5 py-2 text-left hover:bg-(--ui-control-hover-background)',
                    selectedBotIdentity === identity &&
                      'border-(--ui-stroke-tertiary) bg-(--ui-control-active-background)'
                  )}
                  key={bot.key}
                  onClick={() => {
                    setSelectedBotIdentity(identity)
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
              )
            })}
          </div>
        </aside>

        <main className="min-h-0 overflow-y-auto p-5">
          <div className="mx-auto grid max-w-5xl gap-6">
            {selectedBot ? (
              <section
                aria-labelledby="bot-direct-title"
                className="rounded-lg border border-(--ui-stroke-secondary) bg-card p-4"
              >
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
                      <div className="whitespace-pre-wrap text-xs leading-relaxed">
                        {dmReply || '(No visible reply)'}
                      </div>
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
                    <p className="text-[0.6875rem] text-amber-600 dark:text-amber-300">
                      Select at least 2 distinct Bots.
                    </p>
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
                <nav
                  aria-label="Bot rooms"
                  className="border-r border-(--ui-stroke-secondary) p-2 max-[48rem]:border-b max-[48rem]:border-r-0"
                >
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
                        <AlertDescription>
                          {room.pending_user_action
                            ? `@${room.pending_user_action.member} is waiting for your ${room.pending_user_action.kind === 'approval' ? 'approval' : 'answer'}.`
                            : 'A Bot mentioned @user. Reply below to continue the room.'}
                        </AlertDescription>
                      </Alert>
                    ) : null}

                    {room.pending_user_action ? (
                      <section className="m-3 mb-0 grid gap-2 rounded-md border border-amber-500/40 bg-amber-500/5 p-3">
                        <strong className="text-xs">
                          {room.pending_user_action.kind === 'approval'
                            ? room.pending_user_action.description || 'Approve this command?'
                            : room.pending_user_action.question || 'Answer the Bot'}
                        </strong>
                        {room.pending_user_action.command ? (
                          <code className="overflow-x-auto rounded bg-background p-2 text-[0.6875rem]">
                            {room.pending_user_action.command}
                          </code>
                        ) : null}
                        {room.pending_user_action.kind === 'clarify' && room.pending_user_action.choices.length === 0 ? (
                          <Input
                            aria-label="Answer Bot question"
                            disabled={roomResponding}
                            maxLength={100_000}
                            onChange={event => setHandoffText(event.target.value)}
                            value={handoffText}
                          />
                        ) : null}
                        <div className="flex flex-wrap gap-2">
                          {room.pending_user_action.choices.map(choice => (
                            <Button
                              disabled={roomResponding}
                              key={choice}
                              onClick={() => void handleRoomUserAction(choice)}
                              size="sm"
                              variant={choice === 'deny' ? 'destructive' : 'outline'}
                            >
                              {choice}
                            </Button>
                          ))}
                          {room.pending_user_action.kind === 'clarify' && room.pending_user_action.choices.length === 0 ? (
                            <Button
                              disabled={roomResponding || !handoffText.trim()}
                              onClick={() => void handleRoomUserAction(handoffText)}
                              size="sm"
                            >
                              Send answer
                            </Button>
                          ) : null}
                        </div>
                      </section>
                    ) : null}

                    <div aria-label="Room transcript" className="min-h-52 flex-1 space-y-3 overflow-y-auto p-4">
                      {room.messages.length ? (
                        room.messages.map(message => {
                          const authorBot = bots.find(bot => bot.profile === message.profile)

                          const authorName =
                            message.author === 'user' ? 'You' : authorBot?.display_name || `@${message.author}`

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
                                <strong className={message.author === 'user' ? 'text-foreground' : 'text-primary'}>
                                  {authorName}
                                </strong>
                                {message.author !== 'user' ? (
                                  <span className="text-(--ui-text-quaternary)">@{message.author}</span>
                                ) : null}
                                {message.round ? <Badge variant="outline">round {message.round}</Badge> : null}
                                {message.late ? <Badge variant="warn">slow</Badge> : null}
                                <time className="ml-auto text-(--ui-text-quaternary)">
                                  {formatTime(message.created_at)}
                                </time>
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
                      <div
                        aria-label={`Attach files to ${room.name}`}
                        className={cn(
                          'relative rounded-md border border-transparent p-1 transition-colors',
                          roomAttachmentDragActive && 'border-dashed border-primary bg-primary/5'
                        )}
                        onDragEnter={handleRoomAttachmentDragEnter}
                        onDragLeave={handleRoomAttachmentDragLeave}
                        onDragOver={handleRoomAttachmentDragOver}
                        onDrop={handleRoomAttachmentDrop}
                      >
                        {roomAttachmentDragActive ? (
                          <div className="pointer-events-none absolute inset-0 z-10 grid place-items-center rounded-md bg-background/90 text-xs font-medium text-primary">
                            <span className="flex items-center gap-1.5">
                              <Codicon name="cloud-upload" />
                              Drop files to attach
                            </span>
                          </div>
                        ) : null}
                        <Textarea
                          aria-label={`Message ${room.name}`}
                          disabled={roomSending}
                          maxLength={100_000}
                          onChange={event => setRoomText(event.target.value)}
                          placeholder="Message the room. Mention @handle to target a Bot…"
                          value={roomText}
                        />

                        {roomAttachments.length > 0 ? (
                          <div className="mt-2 rounded-md border border-(--ui-stroke-secondary) bg-background p-2">
                            <div className="mb-1.5 flex items-center justify-between gap-2">
                              <span className="text-[0.6875rem] font-medium">
                                Attachments ({roomAttachments.length}/{ROOM_MAX_ATTACHMENTS})
                              </span>
                              <Button
                                aria-label="Clear room attachments"
                                disabled={roomSending}
                                onClick={clearRoomAttachments}
                                size="xs"
                                variant="text"
                              >
                                Clear all
                              </Button>
                            </div>
                            <ul aria-label="Selected room attachments" className="grid gap-1">
                              {roomAttachments.map(attachment => {
                                const overRemoteLimit =
                                  roomHasRemoteMembers && attachment.size > ROOM_REMOTE_ATTACHMENT_BYTES

                                return (
                                  <li
                                    className="flex min-w-0 items-center gap-2 rounded bg-card px-2 py-1.5 text-[0.6875rem]"
                                    key={attachment.path}
                                  >
                                    <Codicon className="shrink-0 text-(--ui-text-tertiary)" name="file" />
                                    <span className="min-w-0 flex-1 truncate" title={attachment.path}>
                                      {attachment.name}
                                    </span>
                                    <Badge variant="outline">{attachment.mime_type}</Badge>
                                    <span className="shrink-0 tabular-nums text-(--ui-text-tertiary)">
                                      {formatFileSize(attachment.size)}
                                    </span>
                                    {overRemoteLimit ? <Badge variant="warn">over remote limit</Badge> : null}
                                    <Button
                                      aria-label={`Remove ${attachment.name}`}
                                      disabled={roomSending}
                                      onClick={() => removeRoomAttachment(attachment.path)}
                                      size="icon-xs"
                                      variant="ghost"
                                    >
                                      <Codicon name="close" />
                                    </Button>
                                  </li>
                                )
                              })}
                            </ul>
                          </div>
                        ) : null}

                        {roomAttachmentIssue ? (
                          <p className="mt-1.5 text-[0.6875rem] text-destructive" role="alert">
                            {roomAttachmentIssue}
                          </p>
                        ) : null}
                        {remoteOversizeAttachments.length > 0 ? (
                          <p className="mt-1.5 text-[0.6875rem] text-amber-600 dark:text-amber-300" role="alert">
                            Remote Bots accept attachments up to 7 MiB. Remove the flagged file
                            {remoteOversizeAttachments.length === 1 ? '' : 's'} before sending; local Bots accept up to
                            25 MiB.
                          </p>
                        ) : null}

                        <div className="mt-2 flex flex-wrap items-end justify-between gap-2">
                          <div className="flex min-w-0 flex-wrap items-center gap-2">
                            <Button
                              disabled={
                                roomSending || roomPickingAttachments || roomAttachments.length >= ROOM_MAX_ATTACHMENTS
                              }
                              onClick={() => void handlePickRoomAttachments()}
                              size="sm"
                              variant="outline"
                            >
                              <Codicon
                                name={roomPickingAttachments ? 'loading' : 'attach'}
                                spinning={roomPickingAttachments}
                              />
                              {roomPickingAttachments ? 'Inspecting…' : 'Attach files'}
                            </Button>
                            <span className="text-[0.65rem] text-(--ui-text-quaternary)">
                              PDF, images, text, or Markdown · {ROOM_MAX_ATTACHMENTS} max · message required
                            </span>
                          </div>
                          <Button
                            disabled={roomSending || !roomText.trim() || remoteOversizeAttachments.length > 0}
                            onClick={() => void handleSendRoomMessage()}
                            size="sm"
                          >
                            <Codicon name={roomSending ? 'loading' : 'send'} spinning={roomSending} />
                            {roomSending ? 'Bots working…' : 'Send to room'}
                          </Button>
                        </div>
                      </div>
                      <div className="mt-1.5 text-[0.65rem] text-(--ui-text-quaternary)">
                        {roomSending
                          ? 'Running serial Bot turns within the room limits…'
                          : 'Drop files here. No mention selects the whole room; new input supersedes stale work.'}
                      </div>
                      {lastTurn ? (
                        <p className="mt-2 text-[0.6875rem] text-(--ui-text-tertiary)">
                          Turn {lastTurn.epoch}: {lastTurn.rounds} round{lastTurn.rounds === 1 ? '' : 's'},{' '}
                          {lastTurn.suppressed} hidden pass/duplicate/failure{lastTurn.suppressed === 1 ? '' : 's'}.
                        </p>
                      ) : null}
                    </div>

                    {room.activity.length ? (
                      <details className="border-t border-(--ui-stroke-secondary) px-4 py-2 text-[0.6875rem]">
                        <summary className="cursor-pointer text-(--ui-text-tertiary)">
                          Private activity ({room.activity.length})
                        </summary>
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
                                variant={
                                  activity.state === 'failed' || activity.state === 'timeout' ? 'destructive' : 'muted'
                                }
                              >
                                {activity.state}
                              </Badge>
                              {typeof activity.elapsed_seconds === 'number' ? (
                                <span>{activity.elapsed_seconds.toFixed(1)}s</span>
                              ) : null}
                              {activity.error ? (
                                <span className="basis-full whitespace-pre-wrap">{activity.error}</span>
                              ) : null}
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
