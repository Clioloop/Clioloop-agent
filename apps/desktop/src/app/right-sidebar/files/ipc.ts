import ignore from 'ignore'

import { type FocusedProjectRoute, scopeProjectRpc } from '@/desktop/remote-lifecycle'
import type { ClioConnection, ClioReadDirEntry, ClioReadDirResult } from '@/global'
import { $connection } from '@/store/session'
import { requestForBackendRoute } from '@/store/session-request-router'

export type ProjectTreeEntry = ClioReadDirEntry
export type GatewayRequest = <T>(
  method: string,
  params?: Record<string, unknown>,
  timeoutMs?: number
) => Promise<T>

export interface ProjectReadContext {
  connection?: ClioConnection | null
  requestGateway?: GatewayRequest
}

interface GitignoreRule {
  base: string
  ig: ReturnType<typeof ignore>
}

interface RemoteProject {
  browse_token: string
  id: string
  name: string
  path: string
}

interface RemoteDiscoverResponse {
  connection_id: string
  profile: string
  projects: RemoteProject[]
  route_key: string
}

interface RemoteTreeResponse extends ClioReadDirResult {
  connection_id: string
  path: string
  profile: string
  root: string
  route_key: string
  truncated?: boolean
}

interface RemoteBrowseGrant {
  browseToken: string
  root: string
  route: FocusedProjectRoute
}

const gitRootCache = new Map<string, Promise<string | null>>()
const gitignoreCache = new Map<string, Promise<GitignoreRule | null>>()
const remoteBrowseGrants = new Map<string, RemoteBrowseGrant>()

function errorMessage(error: unknown): string {
  const raw = error instanceof Error ? error.message : String(error || 'Gateway unavailable')

  return (raw.match(/Error invoking remote method '[^']+': Error: (.+)$/)?.[1] ?? raw)
    .replace(/^Error:\s*/, '')
    .trim()
}

function decodeDataUrl(dataUrl: string) {
  const match = dataUrl.match(/^data:[^,]*,(.*)$/)
  const data = match?.[1] || ''
  const isBase64 = dataUrl.slice(0, dataUrl.indexOf(',')).includes(';base64')

  if (!isBase64) {
    return decodeURIComponent(data)
  }

  const bytes = Uint8Array.from(atob(data), ch => ch.charCodeAt(0))

  return new TextDecoder().decode(bytes)
}

function clean(path: string) {
  return path.replace(/\/+$/, '') || '/'
}

/** Strict POSIX-style relative path; null if `child` is not inside `root`. */
function relativeTo(root: string, child: string) {
  const r = clean(root)
  const c = clean(child)

  if (c === r) {
    return ''
  }

  return c.startsWith(`${r}/`) ? c.slice(r.length + 1) : null
}

/** Repo-root → repo-root/a → repo-root/a/b → … for every dir between root and `dir`. */
function ancestorDirs(root: string, dir: string) {
  const r = clean(root)
  const rel = relativeTo(r, dir)

  if (rel === null || rel === '') {
    return [r]
  }

  const dirs = [r]
  let current = r

  for (const part of rel.split('/').filter(Boolean)) {
    current = `${current}/${part}`
    dirs.push(current)
  }

  return dirs
}

async function gitRootFor(start: string) {
  if (!window.clioDesktop?.gitRoot) {
    return null
  }

  const key = clean(start)
  let cached = gitRootCache.get(key)

  if (!cached) {
    cached = window.clioDesktop.gitRoot(key)
    gitRootCache.set(key, cached)
  }

  return cached
}

/** Read .gitignore at `dir` if it actually exists — never probe missing files. */
async function readGitignore(dir: string): Promise<GitignoreRule | null> {
  if (!window.clioDesktop?.readDir || !window.clioDesktop.readFileDataUrl) {
    return null
  }

  try {
    const listing = await window.clioDesktop.readDir(dir)

    if (!listing.entries.some(e => e.name === '.gitignore' && !e.isDirectory)) {
      return null
    }

    const text = decodeDataUrl(await window.clioDesktop.readFileDataUrl(`${dir}/.gitignore`))

    return { base: dir, ig: ignore().add(text) }
  } catch {
    return null
  }
}

async function gitignoreFor(dir: string) {
  const key = clean(dir)
  let cached = gitignoreCache.get(key)

  if (!cached) {
    cached = readGitignore(key)
    gitignoreCache.set(key, cached)
  }

  return cached
}

function ignoredBy(rules: GitignoreRule[], entry: ClioReadDirEntry) {
  return rules.some(rule => {
    const rel = relativeTo(rule.base, entry.path)

    if (rel === null || rel === '') {
      return false
    }

    return rule.ig.ignores(entry.isDirectory ? `${rel}/` : rel)
  })
}

async function filterIgnored(entries: ClioReadDirEntry[], rootPath: string, dirPath: string) {
  const root = await gitRootFor(rootPath)

  if (!root) {
    return entries
  }

  const rules = (await Promise.all(ancestorDirs(root, dirPath).map(gitignoreFor))).filter((r): r is GitignoreRule =>
    Boolean(r)
  )

  return rules.length > 0 ? entries.filter(entry => !ignoredBy(rules, entry)) : entries
}

function remoteRoute(connection: ClioConnection): FocusedProjectRoute {
  return {
    connectionId: connection.connectionId,
    profile: connection.profile?.trim() || 'default',
    remote: true,
    routeKey: connection.routeKey
  }
}

function assertRouteResponse(route: FocusedProjectRoute, response: Record<string, unknown>): void {
  if (
    response.connection_id !== route.connectionId ||
    response.profile !== route.profile ||
    response.route_key !== route.routeKey
  ) {
    throw new Error('Project response did not match the requested backend route.')
  }
}

function grantKey(route: FocusedProjectRoute, rootPath: string): string {
  return `${route.routeKey}\0${clean(rootPath)}`
}

async function discoverRemoteGrant(
  route: FocusedProjectRoute,
  rootPath: string,
  requestGateway: GatewayRequest
): Promise<RemoteBrowseGrant> {
  const scope = scopeProjectRpc(route, [rootPath])

  const response = await requestForBackendRoute<RemoteDiscoverResponse>(
    route,
    requestGateway,
    'project.discover',
    { ...scope }
  )

  assertRouteResponse(route, response as unknown as Record<string, unknown>)

  const requested = clean(rootPath)
  const project = response.projects.find(candidate => clean(candidate.path) === requested)

  if (!project?.browse_token) {
    throw new Error(`The remote backend did not expose project root "${rootPath}".`)
  }

  const grant = { browseToken: project.browse_token, root: project.path, route }

  remoteBrowseGrants.set(grantKey(route, rootPath), grant)

  return grant
}

function validRemoteEntries(value: unknown): ClioReadDirEntry[] {
  if (!Array.isArray(value)) {
    throw new Error('The remote project tree returned an invalid entry list.')
  }

  return value.map(entry => {
    if (!entry || typeof entry !== 'object') {
      throw new Error('The remote project tree returned an invalid entry.')
    }

    const candidate = entry as Record<string, unknown>

    if (typeof candidate.name !== 'string' || typeof candidate.path !== 'string') {
      throw new Error('The remote project tree returned an invalid path.')
    }

    return { isDirectory: candidate.isDirectory === true, name: candidate.name, path: candidate.path }
  })
}

async function readRemoteProjectDir(
  connection: ClioConnection,
  dirPath: string,
  rootPath: string,
  requestGateway: GatewayRequest
): Promise<ClioReadDirResult> {
  const route = remoteRoute(connection)
  const key = grantKey(route, rootPath)

  const read = async (refreshGrant: boolean): Promise<ClioReadDirResult> => {
    const grant =
      !refreshGrant && remoteBrowseGrants.get(key)
        ? remoteBrowseGrants.get(key)!
        : await discoverRemoteGrant(route, rootPath, requestGateway)

    const response = await requestForBackendRoute<RemoteTreeResponse>(route, requestGateway, 'project.tree', {
      ...scopeProjectRpc(route, [grant.root]),
      browse_token: grant.browseToken,
      path: dirPath
    })

    assertRouteResponse(route, response as unknown as Record<string, unknown>)

    return {
      entries: validRemoteEntries(response.entries),
      ...(response.error ? { error: response.error } : {}),
      ...(response.truncated ? { truncated: true } : {})
    }
  }

  try {
    return await read(false)
  } catch {
    // A browse grant is intentionally short-lived. Rediscover once so an open
    // tree survives expiry; the second error is surfaced verbatim to the UI.
    remoteBrowseGrants.delete(key)

    return read(true)
  }
}

export async function readProjectDir(
  dirPath: string,
  rootPath = dirPath,
  context: ProjectReadContext = {}
): Promise<ClioReadDirResult> {
  if (!window.clioDesktop) {
    return { entries: [], error: 'no-bridge' }
  }

  const connection = context.connection === undefined ? $connection.get() : context.connection

  if (connection?.mode === 'remote') {
    if (!context.requestGateway) {
      return { entries: [], error: 'Remote project gateway is unavailable.' }
    }

    try {
      return await readRemoteProjectDir(connection, dirPath, rootPath, context.requestGateway)
    } catch (error) {
      return { entries: [], error: errorMessage(error) || 'Remote project browser is unavailable.' }
    }
  }

  try {
    const result = await window.clioDesktop.readDir(dirPath)

    return { ...result, entries: await filterIgnored(result.entries, rootPath, dirPath) }
  } catch (error) {
    return { entries: [], error: errorMessage(error) || 'Could not read this folder.' }
  }
}

export function clearProjectDirCache(rootPath?: string, routeKey?: string) {
  if (!rootPath) {
    gitRootCache.clear()
    gitignoreCache.clear()

    if (!routeKey) {
      remoteBrowseGrants.clear()
    } else {
      for (const key of remoteBrowseGrants.keys()) {
        if (key.startsWith(`${routeKey}\0`)) {
          remoteBrowseGrants.delete(key)
        }
      }
    }

    return
  }

  const key = clean(rootPath)
  gitRootCache.delete(key)
  gitignoreCache.delete(key)

  if (routeKey) {
    remoteBrowseGrants.delete(`${routeKey}\0${key}`)
  }
}
