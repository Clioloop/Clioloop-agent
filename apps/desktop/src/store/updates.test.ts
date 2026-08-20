import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { DesktopUpdateStatus } from '@/global'

const storage = new Map<string, string>()

vi.mock('@/lib/storage', () => ({
  persistString: (key: string, value: null | string) => {
    if (value === null) {
      storage.delete(key)
    } else {
      storage.set(key, value)
    }
  },
  storedString: (key: string) => storage.get(key) ?? null
}))

const notifySpy = vi.fn()
const dismissSpy = vi.fn()
const connectedRoutesSpy = vi.fn(() => [] as Array<Record<string, unknown>>)
const requestGatewaySpy = vi.fn()

vi.mock('@/store/gateway', () => ({
  connectedGatewayRoutes: () => connectedRoutesSpy(),
  requestGatewayForProfile: (...args: unknown[]) => requestGatewaySpy(...args)
}))

vi.mock('@/store/notifications', () => ({
  notify: (...args: unknown[]) => notifySpy(...args),
  dismissNotification: (...args: unknown[]) => dismissSpy(...args)
}))

const { $updateApply, applyUpdates, maybeNotifyUpdateAvailable, resetUpdateApplyState } = await import('./updates')

const status = (over: Partial<DesktopUpdateStatus> = {}): DesktopUpdateStatus => ({
  supported: true,
  behind: 3,
  targetSha: 'sha-a',
  fetchedAt: 0,
  ...over
})

const lastToast = () => notifySpy.mock.calls.at(-1)?.[0] as { onDismiss: () => void }

describe('maybeNotifyUpdateAvailable', () => {
  beforeEach(() => {
    storage.clear()
    notifySpy.mockClear()
    vi.useRealTimers()
  })

  it('shows when an update is available and not snoozed', () => {
    maybeNotifyUpdateAvailable(status())
    expect(notifySpy).toHaveBeenCalledTimes(1)
  })

  it('stays quiet for new commits once the toast was closed', () => {
    maybeNotifyUpdateAvailable(status())
    lastToast().onDismiss() // user closes it → cooldown starts
    notifySpy.mockClear()

    // A different commit lands while still within the cooldown window.
    maybeNotifyUpdateAvailable(status({ targetSha: 'sha-b', behind: 9 }))
    expect(notifySpy).not.toHaveBeenCalled()
  })

  it('re-shows once the cooldown elapses', () => {
    vi.useFakeTimers()
    vi.setSystemTime(0)

    maybeNotifyUpdateAvailable(status())
    lastToast().onDismiss()
    notifySpy.mockClear()

    vi.setSystemTime(25 * 60 * 60 * 1000) // > 24h cooldown
    maybeNotifyUpdateAvailable(status({ targetSha: 'sha-b' }))
    expect(notifySpy).toHaveBeenCalledTimes(1)
  })

  it('does nothing when already up to date', () => {
    maybeNotifyUpdateAvailable(status({ behind: 0 }))
    expect(notifySpy).not.toHaveBeenCalled()
  })
})

describe('applyUpdates target fanout', () => {
  const remoteRoute = {
    baseUrl: 'https://remote.example',
    connectionId: 'remote-a',
    label: 'work · remote.example',
    mode: 'remote',
    primary: true,
    profile: 'work',
    routeKey: 'connection:remote-a::profile:work'
  }

  function installBridge(apply: () => Promise<Record<string, unknown>>) {
    Object.defineProperty(window, 'clioDesktop', {
      configurable: true,
      value: { updates: { apply } }
    })
  }

  beforeEach(() => {
    connectedRoutesSpy.mockReset()
    connectedRoutesSpy.mockReturnValue([])
    requestGatewaySpy.mockReset()
    resetUpdateApplyState()
  })

  it('updates remote gateways before the local Desktop app and records each result', async () => {
    const order: string[] = []

    connectedRoutesSpy.mockReturnValue([remoteRoute])
    requestGatewaySpy.mockImplementation(async (_profile, method, params) => {
      order.push(`remote:${method}`)

      return {
        connection_id: params.connection_id,
        ok: true,
        profile: params.profile,
        route_key: params.route_key
      }
    })
    installBridge(async () => {
      order.push('local')

      return { ok: true }
    })

    const result = await applyUpdates()

    expect(result.ok).toBe(true)
    expect(order).toEqual(['remote:system.update', 'local'])
    expect($updateApply.get().targets).toHaveLength(2)
    expect($updateApply.get().targets.every(target => target.ok)).toBe(true)
  })

  it('still runs the local updater but reports a remote target failure', async () => {
    const localApply = vi.fn(async () => ({ ok: true }))

    connectedRoutesSpy.mockReturnValue([remoteRoute])
    requestGatewaySpy.mockRejectedValue(new Error('remote offline'))
    installBridge(localApply)

    const result = await applyUpdates()

    expect(localApply).toHaveBeenCalledTimes(1)
    expect(result.ok).toBe(false)
    expect($updateApply.get().stage).toBe('error')
    expect($updateApply.get().targets.map(target => target.ok)).toEqual([false, true])
  })
})
