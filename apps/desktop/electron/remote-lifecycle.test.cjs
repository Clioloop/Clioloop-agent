'use strict'

const test = require('node:test')
const assert = require('node:assert/strict')

const {
  connectionIdForUrl,
  createRouteSnapshotCache,
  normalizeUpdateTargetResult,
  parseBackendRouteKey,
  routeFor,
  scopeProjectRpc,
  updateBatchSucceeded
} = require('./remote-lifecycle.cjs')

test('canonical routes round-trip and URL identities omit credentials in query/hash', () => {
  const route = routeFor(connectionIdForUrl('https://box.test/clio/?token=secret#x'), ' author ')
  assert.equal(route.connectionId, 'url:https://box.test/clio')
  assert.deepEqual(parseBackendRouteKey(route.routeKey), route)
  assert.equal(parseBackendRouteKey('connection:broken'), null)
})

test('route snapshots retain last-known rows through transport failure', () => {
  const cache = createRouteSnapshotCache()
  const route = routeFor('url:https://box.test', 'default')
  cache.success(route, [{ id: 'session-1' }], 1)
  assert.deepEqual(cache.failure(route, new Error('offline'), 2), {
    ...route,
    error: 'offline',
    items: [{ id: 'session-1' }],
    observedAt: 2,
    stale: true,
    state: 'stale'
  })
})

test('remote project scopes require backend-local roots and canonical routes', () => {
  const route = { ...routeFor('url:https://box.test', 'author'), remote: true }
  assert.throws(() => scopeProjectRpc(route), /backend-local root/)
  assert.deepEqual(scopeProjectRpc(route, [' /srv/repo ', '/srv/repo']), {
    connection_id: route.connectionId,
    profile: 'author',
    roots: ['/srv/repo'],
    route_key: route.routeKey
  })
})

test('update batches require explicit success and reject manual optimism', () => {
  const target = { ...routeFor('local', 'desktop'), kind: 'local-app', label: 'Desktop' }
  const ok = normalizeUpdateTargetResult(target, { ok: true })
  const manual = normalizeUpdateTargetResult(target, { ok: true, manual: true })
  assert.equal(updateBatchSucceeded([ok]), true)
  assert.equal(manual.ok, false)
  assert.equal(manual.skipped, true)
  assert.equal(updateBatchSucceeded([manual]), false)

  const remote = { ...routeFor('url:https://box.test', 'default'), kind: 'remote-backend', label: 'Box' }
  const routed = {
    connection_id: remote.connectionId,
    profile: remote.profile,
    route_key: remote.routeKey
  }
  assert.equal(normalizeUpdateTargetResult(remote, { ...routed, ok: true }).ok, true)
  assert.equal(normalizeUpdateTargetResult(remote, { ...routed, ok: true, profile: 'other' }).ok, false)
})
