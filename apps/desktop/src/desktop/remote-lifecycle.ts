import { backendRouteKey, LOCAL_CONNECTION_ID, profileRouteKey } from './backend-foundations'

export type RouteAvailability = 'healthy' | 'offline' | 'stale'

export interface BackendRoute {
  connectionId: string
  profile: string
  routeKey: string
}

export interface RoutedSnapshot<T> extends BackendRoute {
  error: null | string
  items: T[]
  observedAt: number
  stale: boolean
  state: RouteAvailability
}

/**
 * Last-known-good inventory keyed by the exact (connection, profile) route.
 * A transport outage must not erase sessions/Bots that were already visible;
 * failures retain the roster and mark it stale/offline instead. Never-seen
 * sources stay empty so an unreachable URL cannot invent identities.
 */
export class RouteSnapshotCache<T> {
  readonly #snapshots = new Map<string, RoutedSnapshot<T>>()

  success(route: BackendRoute, items: T[], observedAt = Date.now()): RoutedSnapshot<T> {
    const snapshot: RoutedSnapshot<T> = {
      ...route,
      error: null,
      items: [...items],
      observedAt,
      stale: false,
      state: 'healthy'
    }

    this.#snapshots.set(route.routeKey, snapshot)

    return snapshot
  }

  failure(route: BackendRoute, error: unknown, observedAt = Date.now()): RoutedSnapshot<T> {
    const previous = this.#snapshots.get(route.routeKey)
    const message = error instanceof Error ? error.message : String(error || 'Gateway unavailable')

    const snapshot: RoutedSnapshot<T> = {
      ...route,
      error: message,
      items: previous ? [...previous.items] : [],
      observedAt,
      stale: Boolean(previous),
      state: previous ? 'stale' : 'offline'
    }

    this.#snapshots.set(route.routeKey, snapshot)

    return snapshot
  }

  get(routeKey: string): RoutedSnapshot<T> | null {
    return this.#snapshots.get(routeKey) ?? null
  }

  values(): RoutedSnapshot<T>[] {
    return [...this.#snapshots.values()]
  }

  clear(routeKey?: string): void {
    if (routeKey) {
      this.#snapshots.delete(routeKey)
    } else {
      this.#snapshots.clear()
    }
  }
}

export function routeFor(connectionId?: null | string, profile?: null | string): BackendRoute {
  const normalizedConnection = connectionId?.trim() || LOCAL_CONNECTION_ID
  const normalizedProfile = profileRouteKey(profile)

  return {
    connectionId: normalizedConnection,
    profile: normalizedProfile,
    routeKey: backendRouteKey(normalizedConnection, normalizedProfile)
  }
}

/** Parse only keys emitted by backendRouteKey. Malformed or non-canonical keys
 * fail closed rather than silently falling back to the ambient gateway. */
export function parseBackendRouteKey(routeKey: string): BackendRoute | null {
  const key = String(routeKey || '').trim()

  if (!key) {
    return null
  }

  if (!key.startsWith('connection:')) {
    const route = routeFor(LOCAL_CONNECTION_ID, key)

    return route.routeKey === key ? route : null
  }

  const match = /^connection:([^:]+)::profile:(.+)$/.exec(key)

  if (!match) {
    return null
  }

  try {
    const connectionId = decodeURIComponent(match[1]).trim()
    const profile = decodeURIComponent(match[2]).trim()

    if (!connectionId || !profile) {
      return null
    }

    const route = routeFor(connectionId, profile)

    return route.routeKey === key ? route : null
  } catch {
    return null
  }
}

/** A URL is a stable, secret-free connection identity in Clio's existing
 * per-profile connection model. Profiles sharing one URL share one connection. */
export function connectionIdForUrl(url: string): string {
  const parsed = new URL(url)

  parsed.hash = ''
  parsed.search = ''
  parsed.pathname = parsed.pathname.replace(/\/+$/, '')

  return `url:${parsed.toString().replace(/\/+$/, '')}`
}

export interface FocusedProjectRoute extends BackendRoute {
  remote: boolean
}

export interface ProjectRpcScope {
  connection_id: string
  profile: string
  roots?: string[]
  route_key: string
}

/** Project scans are never allowed to infer roots from the Electron host when
 * the focused backend is remote. Callers must provide backend-local roots. */
export function scopeProjectRpc(
  route: FocusedProjectRoute,
  roots: readonly string[] = []
): ProjectRpcScope {
  const parsed = parseBackendRouteKey(route.routeKey)

  if (!parsed || parsed.connectionId !== route.connectionId || parsed.profile !== route.profile) {
    throw new Error(`Unknown project route "${route.routeKey}".`)
  }

  const normalizedRoots = [...new Set(roots.map(root => String(root).trim()).filter(Boolean))]

  if (route.remote && normalizedRoots.length === 0) {
    throw new Error('Remote project scans require at least one backend-local root.')
  }

  return {
    connection_id: route.connectionId,
    profile: route.profile,
    route_key: route.routeKey,
    ...(normalizedRoots.length ? { roots: normalizedRoots } : {})
  }
}

export type UpdateTargetKind = 'local-app' | 'profile-gateway' | 'remote-backend'

export interface UpdateTarget {
  connectionId: string
  kind: UpdateTargetKind
  label: string
  profile: string
  routeKey: string
}

export interface UpdateTargetResult extends UpdateTarget {
  detail?: string
  error?: string
  ok: boolean
  skipped?: boolean
}

/** Backend action responses are successful only when they explicitly say so.
 * Missing/ambiguous bodies are failures — never optimistic success. */
export function normalizeUpdateTargetResult(
  target: UpdateTarget,
  value: unknown
): UpdateTargetResult {
  const result = value && typeof value === 'object' ? (value as Record<string, unknown>) : {}
  const detail = typeof result.message === 'string' && result.message.trim() ? result.message.trim() : undefined

  // Backend targets only succeed when the authenticated gateway echoes the
  // exact route. This prevents a stale/focused socket response from closing a
  // different target optimistically. Electron-local updater responses predate
  // route metadata and remain governed by their explicit ok flag.
  if (
    target.kind !== 'local-app' &&
    (result.connection_id !== target.connectionId ||
      result.profile !== target.profile ||
      result.route_key !== target.routeKey)
  ) {
    return { ...target, ok: false, error: 'update-route-mismatch', ...(detail ? { detail } : {}) }
  }

  if (result.ok === true && result.manual !== true) {
    return { ...target, ok: true, ...(detail ? { detail } : {}) }
  }

  if (result.manual === true || result.skipped === true) {
    return {
      ...target,
      ok: false,
      skipped: true,
      ...(detail ? { detail } : {}),
      ...(typeof result.error === 'string' ? { error: result.error } : {})
    }
  }

  return {
    ...target,
    ok: false,
    error: typeof result.error === 'string' ? result.error : 'update-not-confirmed',
    ...(detail ? { detail } : {})
  }
}

export function updateBatchSucceeded(results: readonly UpdateTargetResult[]): boolean {
  return results.length > 0 && results.every(result => result.ok)
}
