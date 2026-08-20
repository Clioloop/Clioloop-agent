import {
  activeGatewayProfileKey,
  connectedGatewayRouteForProfile,
  requestGatewayForProfile
} from '@/store/gateway'

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

export interface OwnedBackendRoute {
  connectionId: string
  profile: string
  routeKey: string
}

/** Dispatch on the socket that owns an exact connection/profile route. Profile
 * lookup alone is not enough for remote lifecycle RPCs: a reconfigured profile
 * must fail closed instead of sending its old route key to a new connection. */
export function requestForBackendRoute<T>(
  route: OwnedBackendRoute,
  ambientRequest: <R>(method: string, params?: Record<string, unknown>, timeoutMs?: number) => Promise<R>,
  method: string,
  params: Record<string, unknown> = {},
  timeoutMs?: number
): Promise<T> {
  const registered = connectedGatewayRouteForProfile(route.profile)

  if (
    !registered ||
    registered.connectionId !== route.connectionId ||
    registered.profile !== normKey(route.profile) ||
    registered.routeKey !== route.routeKey
  ) {
    throw new Error(`Gateway unavailable for backend route "${route.routeKey}"`)
  }

  return requestForSessionProfile<T>(route.profile, ambientRequest, method, params, timeoutMs)
}
