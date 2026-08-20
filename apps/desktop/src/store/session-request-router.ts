import { activeGatewayProfileKey, requestGatewayForProfile } from '@/store/gateway'

const normKey = (profile: null | string | undefined): string => (profile ?? '').trim() || 'default'

/** True when a session RPC must bypass the ambient socket and use its owner. */
export function sessionRpcNeedsProfileRoute(
  ownerProfile: null | string | undefined,
  activeProfile: string = activeGatewayProfileKey()
): boolean {
  if (ownerProfile == null || !String(ownerProfile).trim()) {
    return false
  }

  return normKey(ownerProfile) !== normKey(activeProfile)
}

/**
 * Resolve session ownership at request time. The active route may have changed
 * after a wake/switch await, so dispatching through the ambient gateway alone
 * can send resume, usage, prompt, or interrupt RPCs to the wrong backend.
 */
export function requestForSessionProfile<T>(
  ownerProfile: null | string | undefined,
  ambientRequest: <R>(method: string, params?: Record<string, unknown>, timeoutMs?: number) => Promise<R>,
  method: string,
  params: Record<string, unknown> = {},
  timeoutMs?: number
): Promise<T> {
  if (!sessionRpcNeedsProfileRoute(ownerProfile)) {
    return timeoutMs === undefined
      ? ambientRequest<T>(method, params)
      : ambientRequest<T>(method, params, timeoutMs)
  }

  return requestGatewayForProfile<T>(normKey(ownerProfile), method, params, timeoutMs)
}
