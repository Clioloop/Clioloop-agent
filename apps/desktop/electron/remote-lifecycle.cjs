'use strict'

const { backendRouteKey, LOCAL_CONNECTION_ID, profileRouteKey } = require('./backend-foundations.cjs')

function routeFor(connectionId, profile) {
  const normalizedConnection = String(connectionId || '').trim() || LOCAL_CONNECTION_ID
  const normalizedProfile = profileRouteKey(profile)
  return {
    connectionId: normalizedConnection,
    profile: normalizedProfile,
    routeKey: backendRouteKey(normalizedConnection, normalizedProfile)
  }
}

function parseBackendRouteKey(routeKey) {
  const key = String(routeKey || '').trim()
  if (!key) return null

  if (!key.startsWith('connection:')) {
    const route = routeFor(LOCAL_CONNECTION_ID, key)
    return route.routeKey === key ? route : null
  }

  const match = /^connection:([^:]+)::profile:(.+)$/.exec(key)
  if (!match) return null

  try {
    const connectionId = decodeURIComponent(match[1]).trim()
    const profile = decodeURIComponent(match[2]).trim()
    if (!connectionId || !profile) return null
    const route = routeFor(connectionId, profile)
    return route.routeKey === key ? route : null
  } catch {
    return null
  }
}

function connectionIdForUrl(url) {
  const parsed = new URL(url)
  parsed.hash = ''
  parsed.search = ''
  parsed.pathname = parsed.pathname.replace(/\/+$/, '')
  return `url:${parsed.toString().replace(/\/+$/, '')}`
}

function createRouteSnapshotCache() {
  const snapshots = new Map()
  return {
    success(route, items, observedAt = Date.now()) {
      const snapshot = {
        ...route,
        error: null,
        items: [...items],
        observedAt,
        stale: false,
        state: 'healthy'
      }
      snapshots.set(route.routeKey, snapshot)
      return snapshot
    },
    failure(route, error, observedAt = Date.now()) {
      const previous = snapshots.get(route.routeKey)
      const snapshot = {
        ...route,
        error: error instanceof Error ? error.message : String(error || 'Gateway unavailable'),
        items: previous ? [...previous.items] : [],
        observedAt,
        stale: Boolean(previous),
        state: previous ? 'stale' : 'offline'
      }
      snapshots.set(route.routeKey, snapshot)
      return snapshot
    },
    get(routeKey) {
      return snapshots.get(routeKey) || null
    },
    values() {
      return [...snapshots.values()]
    },
    clear(routeKey) {
      if (routeKey) snapshots.delete(routeKey)
      else snapshots.clear()
    }
  }
}

function scopeProjectRpc(route, roots = []) {
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

function normalizeUpdateTargetResult(target, value) {
  const result = value && typeof value === 'object' ? value : {}
  const detail = typeof result.message === 'string' && result.message.trim() ? result.message.trim() : undefined

  if (
    target.kind !== 'local-app' &&
    (result.connection_id !== target.connectionId || result.profile !== target.profile || result.route_key !== target.routeKey)
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

function updateBatchSucceeded(results) {
  return results.length > 0 && results.every(result => result.ok)
}

module.exports = {
  connectionIdForUrl,
  createRouteSnapshotCache,
  normalizeUpdateTargetResult,
  parseBackendRouteKey,
  routeFor,
  scopeProjectRpc,
  updateBatchSucceeded
}
