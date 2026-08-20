import { beforeEach, describe, expect, it, vi } from 'vitest'

const gatewayMocks = vi.hoisted(() => ({
  activeProfile: 'default',
  requestForProfile: vi.fn()
}))

vi.mock('@/store/gateway', () => ({
  activeGatewayProfileKey: () => gatewayMocks.activeProfile,
  requestGatewayForProfile: (...args: unknown[]) => gatewayMocks.requestForProfile(...args)
}))

const { requestForSessionProfile, sessionRpcNeedsProfileRoute } = await import('./session-request-router')

describe('session request routing', () => {
  beforeEach(() => {
    gatewayMocks.activeProfile = 'default'
    gatewayMocks.requestForProfile.mockReset()
  })

  it('uses the ambient request for an unscoped or currently active owner', async () => {
    const ambientRequest = vi.fn().mockResolvedValue('ambient')

    await expect(requestForSessionProfile(undefined, ambientRequest, 'session.usage')).resolves.toBe('ambient')
    await expect(
      requestForSessionProfile(' default ', ambientRequest, 'session.resume', { session_id: 'stored-1' }, 12_000)
    ).resolves.toBe('ambient')

    expect(ambientRequest).toHaveBeenNthCalledWith(1, 'session.usage', {})
    expect(ambientRequest).toHaveBeenNthCalledWith(2, 'session.resume', { session_id: 'stored-1' }, 12_000)
    expect(gatewayMocks.requestForProfile).not.toHaveBeenCalled()
  })

  it('pins a mismatched session owner to its profile without using the ambient route', async () => {
    const ambientRequest = vi.fn()
    gatewayMocks.activeProfile = 'default'
    gatewayMocks.requestForProfile.mockResolvedValue('owned')

    await expect(
      requestForSessionProfile(' bot-profile ', ambientRequest, 'session.resume', { session_id: 'stored-2' })
    ).resolves.toBe('owned')

    expect(ambientRequest).not.toHaveBeenCalled()
    expect(gatewayMocks.requestForProfile).toHaveBeenCalledWith(
      'bot-profile',
      'session.resume',
      { session_id: 'stored-2' },
      undefined
    )
  })

  it('normalizes owner keys when deciding whether a pinned route is required', () => {
    expect(sessionRpcNeedsProfileRoute(' profile-a ', 'profile-a')).toBe(false)
    expect(sessionRpcNeedsProfileRoute('profile-a', 'profile-b')).toBe(true)
    expect(sessionRpcNeedsProfileRoute('   ', 'profile-b')).toBe(false)
  })
})
