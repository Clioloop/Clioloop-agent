import type { ConnectionState, GatewayEvent } from '@clio/shared'
import { atom, batch } from 'nanostores'

import { ClioGateway } from '@/clio'
import type { ClioConnection } from '@/global'
import { resolveGatewayWsUrl } from '@/lib/gateway-ws-url'
import { setConnection, setGatewayState } from '@/store/session'

// ── Multi-profile gateway routing ──────────────────────────────────────────
// Concurrent sessions across profiles need concurrent sockets: the renderer's
// event handler is already session-keyed, so the only thing stopping two
// profiles streaming at once was the single swapping socket. We keep that one
// socket as the PRIMARY (window) backend — owned by use-gateway-boot, with all
// its boot-progress / sleep-wake machinery — and add one persistent SECONDARY
// socket per *other* profile that has live work. Every socket feeds the same
// handleGatewayEvent, so background sessions keep painting. Single-profile users
// only ever have the primary, so their path is byte-for-byte unchanged.

const normKey = (profile: string | null | undefined): string => (profile ?? '').trim() || 'default'

// Read connection state through a call so TS control-flow analysis doesn't
// narrow the getter to a constant across guards (it genuinely changes).
const isOpen = (gateway: ClioGateway | null): gateway is ClioGateway => gateway?.connectionState === 'open'

// The active gateway instance, exposed for inline message-stream components
// (e.g. inline ClarifyTool, model overlays) that call gateway methods without
// the instance threaded down through props.
export const $gateway = atom<ClioGateway | null>(null)

// The gateway registry owns the active profile as well as the active socket.
// Publishing both from setActive() prevents a stale profile atom from claiming
// one backend while outbound RPCs use another.
export const $activeGatewayRoute = atom<string>('default')
export const $activeGatewayProfile = $activeGatewayRoute

/** Secret-free inventory of sockets that are currently open. Update and
 * project UI use this registry rather than guessing routes from the focused
 * Electron connection. */
export interface ConnectedGatewayRoute {
  baseUrl: string
  connectionId: string
  label: string
  mode: 'local' | 'remote'
  primary: boolean
  profile: string
  routeKey: string
}

export const $connectedGatewayRoutes = atom<ConnectedGatewayRoute[]>([])

interface RegistryConfig {
  onEvent: (event: GatewayEvent) => void
}

let config: RegistryConfig | null = null

export function configureGatewayRegistry(cfg: RegistryConfig): void {
  config = cfg
}

// ── Primary (window) backend ───────────────────────────────────────────────
let primaryGateway: ClioGateway | null = null
let primaryProfile = 'default'
let primaryConnection: ClioConnection | null = null

export function setPrimaryGateway(
  gateway: ClioGateway | null,
  profile = 'default',
  connection: ClioConnection | null = primaryConnection
): void {
  primaryGateway = gateway
  primaryProfile = normKey(profile)
  primaryConnection = gateway ? connection : null
  publishConnectedRoutes()
}

export function setPrimaryGatewayConnection(connection: ClioConnection | null): void {
  primaryConnection = connection
  publishConnectedRoutes()
}

// ── Secondary (pool) backends ──────────────────────────────────────────────
interface Secondary {
  profile: string
  connection: ClioConnection | null
  connectPromise: Promise<void> | null
  gateway: ClioGateway
  offEvent: () => void
  offState: () => void
  reconnectTimer: ReturnType<typeof setTimeout> | null
  reconnectAttempt: number
  reconnecting: boolean
  // While true the entry auto-reconnects on drop; pruning flips it off so a
  // deliberate close doesn't trigger the backoff loop.
  wantOpen: boolean
}

const secondaries = new Map<string, Secondary>()

let activeKey = 'default'

function connectedRoute(connection: ClioConnection, profile: string, primary: boolean): ConnectedGatewayRoute {
  const normalizedProfile = normKey(profile)

  return {
    baseUrl: connection.baseUrl,
    connectionId: connection.connectionId,
    label:
      connection.mode === 'remote'
        ? `${normalizedProfile} · ${connection.baseUrl}`
        : primary
          ? `${normalizedProfile} · This device`
          : `${normalizedProfile} profile`,
    mode: connection.mode === 'remote' ? 'remote' : 'local',
    primary,
    profile: normalizedProfile,
    routeKey: connection.routeKey
  }
}

function publishConnectedRoutes(): void {
  const routes: ConnectedGatewayRoute[] = []

  if (primaryConnection && isOpen(primaryGateway)) {
    routes.push(connectedRoute(primaryConnection, primaryProfile, true))
  }

  for (const entry of secondaries.values()) {
    if (entry.connection && isOpen(entry.gateway)) {
      routes.push(connectedRoute(entry.connection, entry.profile, false))
    }
  }

  $connectedGatewayRoutes.set(routes)
}

export function connectedGatewayRoutes(): ConnectedGatewayRoute[] {
  return [...$connectedGatewayRoutes.get()]
}

export function connectedGatewayRouteForProfile(profile: string): ConnectedGatewayRoute | null {
  const key = normKey(profile)

  return $connectedGatewayRoutes.get().find(route => route.profile === key) ?? null
}

export function isActivePrimary(): boolean {
  return activeKey === primaryProfile
}

export function activeGatewayProfileKey(): string {
  return $activeGatewayRoute.get()
}

export function activeGateway(): ClioGateway | null {
  if (activeKey === primaryProfile) {
    return primaryGateway
  }

  return secondaries.get(activeKey)?.gateway ?? null
}

// Mirror a backend's connection state into the global composer state, but only
// when that backend is the one the user is currently looking at. Lets the
// composer reflect the active profile's socket without a background reconnect
// flipping the foreground enabled/disabled state.
function reportGatewayState(profile: string, state: ConnectionState): void {
  if (normKey(profile) === activeKey) {
    setGatewayState(state)
  }
}

export function reportPrimaryGatewayState(state: ConnectionState): void {
  reportGatewayState(primaryProfile, state)
  publishConnectedRoutes()
}

function setActive(profile: string): void {
  const key = normKey(profile)
  const gateway = key === primaryProfile ? primaryGateway : (secondaries.get(key)?.gateway ?? null)

  if (!isOpen(gateway)) {
    throw new Error(`Clio gateway unavailable for profile "${key}"`)
  }

  activeKey = key

  batch(() => {
    $activeGatewayRoute.set(key)
    $gateway.set(gateway)
    const connection = key === primaryProfile ? primaryConnection : (secondaries.get(key)?.connection ?? null)

    if (connection) {
      setConnection(connection)
    }

    setGatewayState(gateway.connectionState)
  })
}

function clearTimer(entry: Secondary): void {
  if (entry.reconnectTimer !== null) {
    clearTimeout(entry.reconnectTimer)
    entry.reconnectTimer = null
  }
}

async function openSecondary(entry: Secondary): Promise<void> {
  if (isOpen(entry.gateway)) {
    return
  }

  if (entry.connectPromise) {
    return entry.connectPromise
  }

  const desktop = window.clioDesktop

  if (!desktop) {
    throw new Error('Desktop IPC bridge is unavailable')
  }

  const pending = (async () => {
    const conn = await desktop.getConnection(entry.profile)
    const wsUrl = await resolveGatewayWsUrl(desktop, conn)

    await entry.gateway.connect(wsUrl)
    entry.connection = conn
    publishConnectedRoutes()

    if (!entry.wantOpen) {
      entry.gateway.close()
      throw new Error(`Gateway profile "${entry.profile}" was retired while connecting.`)
    }

    void desktop.touchBackend?.(entry.profile).catch(() => undefined)
  })()

  entry.connectPromise = pending

  try {
    await pending
  } finally {
    if (entry.connectPromise === pending) {
      entry.connectPromise = null
    }
  }
}

function scheduleReconnect(entry: Secondary): void {
  if (entry.reconnecting || entry.reconnectTimer !== null || !entry.wantOpen) {
    return
  }

  // 1s, 2s, 4s … capped at 15s — same backoff shape as the primary.
  const delay = Math.min(15_000, 1_000 * 2 ** Math.min(entry.reconnectAttempt, 4))
  entry.reconnectAttempt += 1
  entry.reconnectTimer = setTimeout(() => {
    entry.reconnectTimer = null
    void reconnectSecondary(entry)
  }, delay)
}

async function reconnectSecondary(entry: Secondary): Promise<void> {
  if (entry.reconnecting || !entry.wantOpen || isOpen(entry.gateway)) {
    return
  }

  entry.reconnecting = true

  try {
    await openSecondary(entry)
    entry.reconnectAttempt = 0
  } catch {
    // Transport failure → fall through to the backoff below.
  } finally {
    entry.reconnecting = false

    if (entry.wantOpen && !isOpen(entry.gateway)) {
      scheduleReconnect(entry)
    }
  }
}

function createSecondary(profile: string): Secondary {
  const gateway = new ClioGateway()

  const entry: Secondary = {
    profile,
    connection: null,
    connectPromise: null,
    gateway,
    offEvent: () => {},
    offState: () => {},
    reconnectTimer: null,
    reconnectAttempt: 0,
    reconnecting: false,
    wantOpen: true
  }

  entry.offEvent = gateway.onEvent(event => config?.onEvent(event))
  entry.offState = gateway.onState(state => {
    reportGatewayState(profile, state)

    if (state === 'open') {
      entry.reconnectAttempt = 0
      clearTimer(entry)
    } else if ((state === 'closed' || state === 'error') && entry.wantOpen) {
      scheduleReconnect(entry)
    }

    publishConnectedRoutes()
  })

  secondaries.set(profile, entry)

  return entry
}

async function gatewayForProfile(profile: string): Promise<ClioGateway> {
  const key = normKey(profile)

  if (key === primaryProfile) {
    if (!isOpen(primaryGateway)) {
      throw new Error(`Clio gateway unavailable for profile "${key}"`)
    }

    return primaryGateway
  }

  let entry = secondaries.get(key)

  if (!entry) {
    entry = createSecondary(key)
  }

  entry.wantOpen = true

  if (!isOpen(entry.gateway)) {
    clearTimer(entry)
    entry.reconnectAttempt = 0

    try {
      await openSecondary(entry)
    } catch (error) {
      scheduleReconnect(entry)
      throw error
    }
  }

  return entry.gateway
}

/** Open a profile's owning socket without changing the foreground/API home. */
export async function openGatewayForProfile(profile: string): Promise<void> {
  await gatewayForProfile(profile)
}

// Make `profile` the active gateway, lazily opening its socket if needed. The
// previous active route remains published when lookup/connection fails.
export async function ensureGatewayForProfile(profile: string): Promise<void> {
  const key = normKey(profile)

  await gatewayForProfile(key)
  setActive(key)
}

/** Dispatch directly on a profile's owning socket without moving the active route. */
export async function requestGatewayForProfile<T>(
  profile: string,
  method: string,
  params: Record<string, unknown> = {},
  timeoutMs?: number
): Promise<T> {
  const gateway = await gatewayForProfile(profile)

  return timeoutMs === undefined
    ? gateway.request<T>(method, params)
    : gateway.request<T>(method, params, timeoutMs)
}

// Reconnect the active gateway after a transient request failure. Primary
// reconnects are owned by use-gateway-boot, so we only drive secondaries here.
export async function ensureActiveGatewayOpen(): Promise<ClioGateway | null> {
  if (activeKey === primaryProfile) {
    return primaryGateway
  }

  const entry = secondaries.get(activeKey)

  if (!entry) {
    return null
  }

  if (!isOpen(entry.gateway)) {
    await reconnectSecondary(entry)
  }

  return isOpen(entry.gateway) ? entry.gateway : null
}

// Wake signal (sleep/network/visibility): nudge every live secondary back open.
export function reconnectSecondaryGateways(): void {
  for (const entry of secondaries.values()) {
    if (!entry.wantOpen || isOpen(entry.gateway)) {
      continue
    }

    entry.reconnectAttempt = 0
    clearTimer(entry)
    void reconnectSecondary(entry)
  }
}

// Keep the idle reaper from killing a backend we still need: ping every live
// secondary. The active one is pinged separately (touchActiveGatewayBackend).
export function touchSecondaryGateways(): void {
  const desktop = window.clioDesktop

  for (const entry of secondaries.values()) {
    if (entry.wantOpen) {
      void desktop?.touchBackend?.(entry.profile).catch(() => undefined)
    }
  }
}

// Close + evict secondaries whose profile is neither active nor in `keep`
// (profiles with a running / needs-input session). Bounds cost to live work.
export function pruneSecondaryGateways(keep: Set<string>): void {
  for (const [key, entry] of [...secondaries]) {
    if (key === activeKey || keep.has(key)) {
      continue
    }

    entry.wantOpen = false
    clearTimer(entry)
    entry.offEvent()
    entry.offState()
    entry.gateway.close()
    secondaries.delete(key)
  }

  publishConnectedRoutes()
}

export function closeSecondaryGateways(): void {
  const activeWasSecondary = activeKey !== primaryProfile

  for (const entry of secondaries.values()) {
    entry.wantOpen = false
    clearTimer(entry)
    entry.offEvent()
    entry.offState()
    entry.gateway.close()
  }

  secondaries.clear()
  publishConnectedRoutes()

  if (activeWasSecondary && isOpen(primaryGateway)) {
    setActive(primaryProfile)
  }
}
