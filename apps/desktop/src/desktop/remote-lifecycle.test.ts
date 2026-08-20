import { describe, expect, it } from 'vitest'

import {
  connectionIdForUrl,
  normalizeUpdateTargetResult,
  parseBackendRouteKey,
  routeFor,
  RouteSnapshotCache,
  scopeProjectRpc,
  updateBatchSucceeded,
  type UpdateTarget
} from './remote-lifecycle'

describe('remote lifecycle routing', () => {
  it('round-trips canonical local and remote route keys and rejects unknown shapes', () => {
    const remote = routeFor('lab/one', ' author ')

    expect(remote.routeKey).toBe('connection:lab%2Fone::profile:author')
    expect(parseBackendRouteKey(remote.routeKey)).toEqual(remote)
    expect(parseBackendRouteKey('author')).toEqual(routeFor('local', 'author'))
    expect(parseBackendRouteKey('connection:lab::profile:')).toBeNull()
    expect(parseBackendRouteKey('connection:%E0%A4%A::profile:author')).toBeNull()
  })

  it('uses normalized URLs as stable secret-free connection identities', () => {
    expect(connectionIdForUrl('https://box.test/clio/?token=never-store#x')).toBe('url:https://box.test/clio')
  })

  it('retains last-known rows through an outage with explicit stale/offline state', () => {
    const cache = new RouteSnapshotCache<{ id: string }>()
    const route = routeFor('lab', 'default')

    expect(cache.failure(route, new Error('down'), 1)).toMatchObject({ items: [], stale: false, state: 'offline' })
    cache.success(route, [{ id: 'session-1' }], 2)

    expect(cache.failure(route, new Error('down again'), 3)).toMatchObject({
      error: 'down again',
      items: [{ id: 'session-1' }],
      stale: true,
      state: 'stale'
    })
  })

  it('requires explicit backend-local roots for remote project scans', () => {
    const route = { ...routeFor('lab', 'author'), remote: true }

    expect(() => scopeProjectRpc(route)).toThrow(/backend-local root/)
    expect(scopeProjectRpc(route, [' /srv/repo ', '/srv/repo'])).toEqual({
      connection_id: 'lab',
      profile: 'author',
      roots: ['/srv/repo'],
      route_key: route.routeKey
    })
    expect(() => scopeProjectRpc({ ...route, routeKey: 'default' }, ['/srv/repo'])).toThrow(/Unknown project route/)
  })
})

describe('remote lifecycle updates', () => {
  const target: UpdateTarget = {
    connectionId: 'lab',
    kind: 'remote-backend',
    label: 'Lab',
    profile: 'default',
    routeKey: routeFor('lab', 'default').routeKey
  }

  it('never turns an ambiguous or manual update response into success', () => {
    expect(normalizeUpdateTargetResult(target, {})).toMatchObject({ ok: false, error: 'update-not-confirmed' })
    expect(normalizeUpdateTargetResult(target, { ok: true, manual: true, message: 'run clio update' })).toMatchObject({
      ok: false,
      skipped: true
    })
    expect(normalizeUpdateTargetResult(target, { ok: true })).toMatchObject({ ok: true })
    expect(updateBatchSucceeded([normalizeUpdateTargetResult(target, { ok: true })])).toBe(true)
    expect(updateBatchSucceeded([normalizeUpdateTargetResult(target, {})])).toBe(false)
  })
})
