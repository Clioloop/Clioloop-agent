import { describe, expect, it } from 'vitest'

import {
  backendRouteKey,
  lifecycleFor,
  LivenessTracker,
  nextCrashJournalEntry,
  normalizeActiveWork,
  normalizeConnectionRegistry,
  quitPromptFor
} from './backend-foundations'

describe('desktop backend foundations', () => {
  it('normalizes a registry without allowing corrupt entries to block local boot', () => {
    const registry = normalizeConnectionRegistry({
      primaryId: 'missing',
      connections: [
        { id: 'edge', kind: 'url', label: 'Edge', url: 'https://example.test/gateway/' },
        { id: 'duplicate', kind: 'ssh', label: 'edge', host: 'ignored' },
        { id: 'bad', kind: 'ssh', label: 'Bad', host: '', port: 99 }
      ]
    })
    expect(registry.primaryId).toBe('local')
    expect(registry.connections.map(connection => connection.id)).toEqual(['local', 'edge'])
    expect(registry.connections[1]).toMatchObject({ url: 'https://example.test/gateway', authMode: 'token' })
  })

  it('keeps local route keys compatible and scopes non-local profiles', () => {
    expect(backendRouteKey('local', ' author ')).toBe('author')
    expect(backendRouteKey('lab/one', ' author ')).toBe('connection:lab%2Fone::profile:author')
    expect(lifecycleFor({ id: 'local', kind: 'local', label: 'This device' }, 'author')).toMatchObject({
      kind: 'local',
      routeKey: 'author',
      args: ['--profile', 'author', 'gateway', '--port', '0']
    })
  })

  it('tracks liveness independently by route and resets a streak after success', () => {
    const tracker = new LivenessTracker(2)
    expect(tracker.record('a', false, null, 1).state).toBe('degraded')
    expect(tracker.record('a', false, null, 2).state).toBe('offline')
    expect(tracker.record('b', true, 12, 3)).toMatchObject({ state: 'healthy', failures: 0, latencyMs: 12 })
    expect(tracker.record('a', true, 4, 4).failures).toBe(0)
  })

  it('provides defensive quit and crash-journal primitives with Clio copy', () => {
    const work = normalizeActiveWork({ count: 2, titles: [' Build ', 'Build', 'Test'] })
    expect(work).toEqual({ count: 2, titles: ['Build', 'Test'] })
    expect(quitPromptFor(work)?.message).toBe('Clio is still working on 2 chats.')
    expect(nextCrashJournalEntry('quit', { at: 7 })).toEqual({ version: 1, at: 7, clean: true, phase: 'quit' })
  })
})
