/**
 * Typed, Electron-free contracts for the next desktop backend layer.
 *
 * The shipping shell remains CommonJS. `electron/backend-foundations.cjs` is
 * its deliberately small runtime bridge; this module is the typed source of
 * truth for renderer/main boundaries and pure policy. Transport and Git side
 * effects are intentionally injected by later slices.
 */

export const CONNECTION_REGISTRY_VERSION = 1 as const
export const LOCAL_CONNECTION_ID = 'local' as const

export type ConnectionKind = 'local' | 'url' | 'ssh'
export type ConnectionHealth = 'unknown' | 'checking' | 'healthy' | 'degraded' | 'offline'

interface ConnectionBase {
  id: string
  label: string
  health?: ConnectionHealth
}

export interface LocalConnection extends ConnectionBase {
  kind: 'local'
  profile?: string | null
}

export interface UrlConnection extends ConnectionBase {
  kind: 'url'
  url: string
  authMode: 'oauth' | 'token'
  tokenKey?: string
}

export interface SshConnection extends ConnectionBase {
  kind: 'ssh'
  host: string
  port?: number
  user?: string
  identityFile?: string
  remoteCommand?: string
}

export type RegistryConnection = LocalConnection | SshConnection | UrlConnection

export interface ConnectionRegistry {
  version: typeof CONNECTION_REGISTRY_VERSION
  primaryId: string
  connections: RegistryConnection[]
}

export function connectionLabelKey(label: string): string {
  return label.trim().toLocaleLowerCase()
}

export function profileRouteKey(profile?: null | string): string {
  return profile?.trim() || 'default'
}

/** Stable key for a (connection, profile) backend. Local keys stay compatible
 * with the existing profile-only pool; remote sources cannot collide. */
export function backendRouteKey(connectionId?: null | string, profile?: null | string): string {
  const profileKey = profileRouteKey(profile)
  const connectionKey = connectionId?.trim()

  return !connectionKey || connectionKey === LOCAL_CONNECTION_ID
    ? profileKey
    : `connection:${encodeURIComponent(connectionKey)}::profile:${encodeURIComponent(profileKey)}`
}

export function normalizeConnectionRegistry(raw: unknown): ConnectionRegistry {
  const source = raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : {}
  const input = Array.isArray(source.connections) ? source.connections : []
  const labels = new Set<string>()
  const ids = new Set<string>()
  const connections: RegistryConnection[] = []

  for (const candidate of input) {
    if (!candidate || typeof candidate !== 'object') {continue}
    const value = candidate as Record<string, unknown>
    const kind = value.kind
    const id = String(value.id || '').trim()
    const label = String(value.label || '').trim()

    if (!id || !label || ids.has(id) || labels.has(connectionLabelKey(label))) {continue}

    let connection: RegistryConnection | null = null

    if (kind === 'local' && id === LOCAL_CONNECTION_ID) {
      connection = { id, kind, label, profile: typeof value.profile === 'string' ? value.profile : null }
    } else if (kind === 'url') {
      try {
        const url = new URL(String(value.url || ''))

        if (url.protocol === 'http:' || url.protocol === 'https:') {
          url.hash = ''
          connection = {
            id,
            kind,
            label,
            url: url.toString().replace(/\/$/, ''),
            authMode: value.authMode === 'oauth' ? 'oauth' : 'token',
            ...(typeof value.tokenKey === 'string' ? { tokenKey: value.tokenKey } : {})
          }
        }
      } catch {
        // Corrupt entries are skipped; they must never prevent local boot.
      }
    } else if (kind === 'ssh') {
      const host = String(value.host || '').trim()
      const port = Number(value.port || 22)

      if (host && Number.isInteger(port) && port > 0 && port <= 65_535) {
        connection = {
          id,
          kind,
          label,
          host,
          port,
          ...(typeof value.user === 'string' && value.user.trim() ? { user: value.user.trim() } : {}),
          ...(typeof value.identityFile === 'string' && value.identityFile.trim()
            ? { identityFile: value.identityFile.trim() }
            : {}),
          ...(typeof value.remoteCommand === 'string' && value.remoteCommand.trim()
            ? { remoteCommand: value.remoteCommand.trim() }
            : {})
        }
      }
    }

    if (!connection) {continue}
    ids.add(id)
    labels.add(connectionLabelKey(label))
    connections.push(connection)
  }

  if (!connections.some(connection => connection.id === LOCAL_CONNECTION_ID)) {
    connections.unshift({ id: LOCAL_CONNECTION_ID, kind: 'local', label: 'This device' })
  }

  const requestedPrimary = String(source.primaryId || '')

  const primaryId = connections.some(connection => connection.id === requestedPrimary)
    ? requestedPrimary
    : LOCAL_CONNECTION_ID

  return { version: CONNECTION_REGISTRY_VERSION, primaryId, connections }
}

/** Opaque envelope. Main-process implementations may use Electron safeStorage,
 * a platform keychain, or a test double; renderers only persist the key. */
export interface EncryptedTokenEnvelope {
  algorithm: string
  ciphertext: string
  version: 1
}

export interface EncryptedTokenStorage {
  delete(key: string): Promise<void>
  get(key: string): Promise<null | string>
  set(key: string, plaintext: string): Promise<void>
}

export type LifecycleDescriptor = LocalLifecycleDescriptor | SshLifecycleDescriptor | UrlLifecycleDescriptor

interface LifecycleBase {
  connectionId: string
  profile: null | string
  routeKey: string
}

export interface LocalLifecycleDescriptor extends LifecycleBase {
  kind: 'local'
  ownership: 'desktop'
  command: string
  args: string[]
}

export interface UrlLifecycleDescriptor extends LifecycleBase {
  kind: 'url'
  ownership: 'external'
  baseUrl: string
}

export interface SshLifecycleDescriptor extends LifecycleBase {
  kind: 'ssh'
  ownership: 'desktop-remote'
  host: string
  port: number
  user?: string
  remoteCommand: string
}

export function lifecycleFor(connection: RegistryConnection, profile?: null | string): LifecycleDescriptor {
  const normalizedProfile = profile?.trim() || null

  const base = {
    connectionId: connection.id,
    profile: normalizedProfile,
    routeKey: backendRouteKey(connection.id, normalizedProfile)
  }

  if (connection.kind === 'url') {
    return { ...base, kind: 'url', ownership: 'external', baseUrl: connection.url }
  }

  if (connection.kind === 'ssh') {
    return {
      ...base,
      kind: 'ssh',
      ownership: 'desktop-remote',
      host: connection.host,
      port: connection.port ?? 22,
      ...(connection.user ? { user: connection.user } : {}),
      remoteCommand: connection.remoteCommand || 'clio gateway --port 0'
    }
  }

  return {
    ...base,
    kind: 'local',
    ownership: 'desktop',
    command: 'clio',
    args: normalizedProfile ? ['--profile', normalizedProfile, 'gateway', '--port', '0'] : ['gateway', '--port', '0']
  }
}

export interface HealthObservation {
  checkedAt: number
  failures: number
  latencyMs: number | null
  state: ConnectionHealth
}

export class LivenessTracker {
  readonly #failureLimit: number
  readonly #routes = new Map<string, HealthObservation>()

  constructor(failureLimit = 3) {
    if (!Number.isInteger(failureLimit) || failureLimit < 1) {throw new Error('failureLimit must be a positive integer')}
    this.#failureLimit = failureLimit
  }

  record(routeKey: string, ok: boolean, latencyMs: number | null, checkedAt = Date.now()): HealthObservation {
    const previous = this.#routes.get(routeKey)
    const failures = ok ? 0 : (previous?.failures ?? 0) + 1
    const state: ConnectionHealth = ok ? 'healthy' : failures >= this.#failureLimit ? 'offline' : 'degraded'
    const observation = { checkedAt, failures, latencyMs: ok ? latencyMs : null, state }
    this.#routes.set(routeKey, observation)

    return observation
  }

  get(routeKey: string): HealthObservation | null {
    return this.#routes.get(routeKey) ?? null
  }

  clear(routeKey?: string): void {
    if (routeKey) {this.#routes.delete(routeKey)}
    else {this.#routes.clear()}
  }
}

export const DESKTOP_IPC = {
  projectsList: 'clio:projects:list',
  projectAdd: 'clio:projects:add',
  worktreesList: 'clio:worktrees:list',
  worktreeCreate: 'clio:worktrees:create',
  worktreeRemove: 'clio:worktrees:remove',
  reviewList: 'clio:git-review:list',
  reviewDiff: 'clio:git-review:diff',
  reviewStage: 'clio:git-review:stage',
  reviewCommit: 'clio:git-review:commit'
} as const

export interface ProjectDescriptor { id: string; name: string; path: string; connectionId?: string }
export interface WorktreeDescriptor { path: string; branch: null | string; isMain: boolean; locked: boolean }
export interface ReviewFile { path: string; added: number; removed: number; staged: boolean; status: string }
export type ReviewScope = 'branch' | 'last-turn' | 'uncommitted'

export interface DesktopBackendIpcContract {
  [DESKTOP_IPC.projectsList]: { request: { connectionId?: string }; response: ProjectDescriptor[] }
  [DESKTOP_IPC.projectAdd]: { request: { path: string }; response: ProjectDescriptor }
  [DESKTOP_IPC.worktreesList]: { request: { projectPath: string }; response: WorktreeDescriptor[] }
  [DESKTOP_IPC.worktreeCreate]: {
    request: { projectPath: string; name: string; base?: string; branch?: string }
    response: WorktreeDescriptor
  }
  [DESKTOP_IPC.worktreeRemove]: { request: { projectPath: string; worktreePath: string; force?: boolean }; response: { ok: boolean } }
  [DESKTOP_IPC.reviewList]: {
    request: { projectPath: string; scope: ReviewScope; baseRef?: string }
    response: { base: null | string; files: ReviewFile[] }
  }
  [DESKTOP_IPC.reviewDiff]: {
    request: { projectPath: string; path: string; scope: ReviewScope; baseRef?: string; staged?: boolean }
    response: string
  }
  [DESKTOP_IPC.reviewStage]: { request: { projectPath: string; paths: string[]; staged: boolean }; response: { ok: boolean } }
  [DESKTOP_IPC.reviewCommit]: { request: { projectPath: string; message: string }; response: { sha: string } }
}

export interface ActiveWork { count: number; titles: string[] }
export interface QuitPrompt { detail: string; message: string }

export function normalizeActiveWork(value: unknown): ActiveWork {
  if (!value || typeof value !== 'object') {return { count: 0, titles: [] }}
  const raw = value as { count?: unknown; titles?: unknown }

  const titles = Array.isArray(raw.titles)
    ? [...new Set(raw.titles.filter((title): title is string => typeof title === 'string').map(title => title.trim()).filter(Boolean))]
    : []

  const count = typeof raw.count === 'number' && Number.isFinite(raw.count) ? Math.max(0, Math.floor(raw.count)) : 0

  return { count: Math.max(count, titles.length), titles }
}

export function quitPromptFor(work: ActiveWork, handoff = false): QuitPrompt | null {
  if (handoff || work.count === 0) {return null}
  const listed = work.titles.slice(0, 4)
  const remaining = work.count - listed.length
  const lines = listed.map(title => `• ${title}`)

  if (remaining > 0) {lines.push(`• ${remaining} more`)}

  return {
    message: `Clio is still working on ${work.count} ${work.count === 1 ? 'chat' : 'chats'}.`,
    detail: `${lines.length ? `${lines.join('\n')}\n\n` : ''}Quitting stops active work and may leave a tool operation incomplete.`
  }
}

export interface CrashJournalEntry {
  at: number
  clean: boolean
  phase: 'boot' | 'ready' | 'quit' | 'runtime'
  reason?: string
  version: 1
}

export function nextCrashJournalEntry(
  phase: CrashJournalEntry['phase'],
  options: { at?: number; clean?: boolean; reason?: unknown } = {}
): CrashJournalEntry {
  const reason = options.reason instanceof Error ? options.reason.stack || options.reason.message : String(options.reason ?? '').trim()

  return {
    version: 1,
    at: options.at ?? Date.now(),
    clean: options.clean ?? phase === 'quit',
    phase,
    ...(reason ? { reason: reason.slice(0, 8_192) } : {})
  }
}
