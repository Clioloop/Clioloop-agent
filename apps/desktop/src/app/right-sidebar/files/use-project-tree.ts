import { useStore } from '@nanostores/react'
import { atom } from 'nanostores'
import { useCallback, useEffect, useMemo } from 'react'

import type { RouteAvailability } from '@/desktop/remote-lifecycle'
import type { ClioConnection } from '@/global'

import { clearProjectDirCache, type GatewayRequest, type ProjectReadContext, readProjectDir } from './ipc'

export interface TreeNode {
  /** Absolute filesystem path. Doubles as react-arborist node id. */
  id: string
  name: string
  /** Drives arborist's leaf-vs-expandable decision via childrenAccessor. */
  isDirectory: boolean
  /** `undefined` = directory, children not yet loaded. `[]` = loaded empty. */
  children?: TreeNode[]
  /** True while a directory read for this folder is in flight. */
  loading?: boolean
  /** Explicit last error from the owning filesystem/gateway. */
  error?: string
}

const PLACEHOLDER_ID = '__loading__'

function makeNode(path: string, name: string, isDirectory: boolean): TreeNode {
  return { id: path, isDirectory, name }
}

function patchNode(nodes: TreeNode[] | undefined | null, id: string, patch: (n: TreeNode) => TreeNode): TreeNode[] {
  if (!nodes) {
    return []
  }

  return nodes.map(n => {
    if (n.id === id) {
      return patch(n)
    }

    if (n.children && n.children.length > 0) {
      return { ...n, children: patchNode(n.children, id, patch) }
    }

    return n
  })
}

function placeholderChild(parentId: string): TreeNode {
  return { id: `${parentId}::${PLACEHOLDER_ID}`, isDirectory: false, name: 'Loading…' }
}

export interface UseProjectTreeOptions {
  connection?: ClioConnection | null
  requestGateway?: GatewayRequest
}

export interface UseProjectTreeResult {
  /** Bumped by collapseAll so callers can remount the tree fully collapsed. */
  collapseNonce: number
  data: TreeNode[]
  openState: Record<string, boolean>
  rootAvailability: RouteAvailability
  rootError: string | null
  rootLoading: boolean
  rootStale: boolean
  rootTruncated: boolean
  collapseAll: () => void
  loadChildren: (id: string) => Promise<void>
  refreshRoot: () => Promise<void>
  setNodeOpen: (id: string, open: boolean) => void
}

interface ProjectTreeState {
  availability: RouteAvailability
  collapseNonce: number
  data: TreeNode[]
  loaded: boolean
  openState: Record<string, boolean>
  requestId: number
  rootError: string | null
  rootLoading: boolean
  scopeKey: string
  stale: boolean
  truncated: boolean
}

const initialState: ProjectTreeState = {
  availability: 'healthy',
  collapseNonce: 0,
  data: [],
  loaded: false,
  openState: {},
  requestId: 0,
  rootError: null,
  rootLoading: false,
  scopeKey: '',
  stale: false,
  truncated: false
}

const inflight = new Set<string>()
const $projectTree = atom<ProjectTreeState>(initialState)
let nextRootRequestId = 0

function setProjectTree(updater: (current: ProjectTreeState) => ProjectTreeState) {
  $projectTree.set(updater($projectTree.get()))
}

function clearProjectTree() {
  nextRootRequestId += 1
  inflight.clear()
  $projectTree.set({ ...initialState, requestId: nextRootRequestId })
}

function projectScopeKey(cwd: string, connection?: ClioConnection | null): string {
  return cwd ? `${connection?.routeKey ?? 'local'}\0${cwd}` : ''
}

function projectContext(options: UseProjectTreeOptions): ProjectReadContext {
  return { connection: options.connection, requestGateway: options.requestGateway }
}

async function loadRoot(
  cwd: string,
  options: UseProjectTreeOptions,
  { force = false }: { force?: boolean } = {}
) {
  if (!cwd) {
    clearProjectTree()

    return
  }

  const scopeKey = projectScopeKey(cwd, options.connection)
  const current = $projectTree.get()

  if (!force && current.scopeKey === scopeKey && (current.loaded || current.rootLoading)) {
    return
  }

  const requestId = nextRootRequestId + 1
  nextRootRequestId = requestId
  inflight.clear()

  if (force || current.scopeKey !== scopeKey) {
    clearProjectDirCache(cwd, options.connection?.routeKey)
  }

  const preserveSnapshot = force && current.scopeKey === scopeKey && current.loaded

  $projectTree.set({
    availability: preserveSnapshot ? current.availability : 'healthy',
    collapseNonce: current.collapseNonce,
    data: preserveSnapshot ? current.data : [],
    loaded: preserveSnapshot,
    openState: current.scopeKey === scopeKey ? current.openState : {},
    requestId,
    rootError: null,
    rootLoading: true,
    scopeKey,
    stale: preserveSnapshot ? current.stale : false,
    truncated: preserveSnapshot ? current.truncated : false
  })

  const { entries, error, truncated } = await readProjectDir(cwd, cwd, projectContext(options))

  setProjectTree(latest => {
    if (latest.scopeKey !== scopeKey || latest.requestId !== requestId) {
      return latest
    }

    if (error) {
      return {
        ...latest,
        availability: latest.loaded ? 'stale' : 'offline',
        loaded: true,
        rootError: error,
        rootLoading: false,
        stale: latest.loaded
      }
    }

    return {
      ...latest,
      availability: 'healthy',
      data: entries.map(e => makeNode(e.path, e.name, e.isDirectory)),
      loaded: true,
      rootError: null,
      rootLoading: false,
      stale: false,
      truncated: Boolean(truncated)
    }
  })
}

export function resetProjectTreeState() {
  clearProjectTree()
  clearProjectDirCache()
}

/**
 * Lazy-loads a directory tree rooted at `cwd`. Remote reads are dispatched on
 * the exact owning connection/profile gateway; local reads retain the Electron
 * filesystem path. A successful snapshot survives transport errors and is
 * marked stale rather than disappearing optimistically.
 */
export function useProjectTree(cwd: string, options: UseProjectTreeOptions = {}): UseProjectTreeResult {
  const state = useStore($projectTree)
  const scopeKey = projectScopeKey(cwd, options.connection)
  const routeKey = options.connection?.routeKey
  const requestGateway = options.requestGateway
  const connection = options.connection

  const refreshRoot = useCallback(
    () => loadRoot(cwd, { connection, requestGateway }, { force: true }),
    [connection, cwd, requestGateway]
  )

  const setNodeOpen = useCallback(
    (id: string, open: boolean) => {
      setProjectTree(current => {
        if (current.scopeKey !== scopeKey || current.openState[id] === open) {
          return current
        }

        return {
          ...current,
          openState: {
            ...current.openState,
            [id]: open
          }
        }
      })
    },
    [scopeKey]
  )

  const collapseAll = useCallback(() => {
    setProjectTree(current => {
      if (current.scopeKey !== scopeKey) {
        return current
      }

      return { ...current, collapseNonce: current.collapseNonce + 1, openState: {} }
    })
  }, [scopeKey])

  const loadChildren = useCallback(
    async (id: string) => {
      const inflightKey = `${scopeKey}\0${id}`

      if (!cwd || inflight.has(inflightKey)) {
        return
      }

      inflight.add(inflightKey)

      setProjectTree(current => {
        if (current.scopeKey !== scopeKey) {
          return current
        }

        return {
          ...current,
          data: patchNode(current.data, id, n => ({ ...n, loading: true, children: [placeholderChild(n.id)] }))
        }
      })

      const { entries, error } = await readProjectDir(id, cwd, { connection, requestGateway })

      inflight.delete(inflightKey)

      setProjectTree(current => {
        if (current.scopeKey !== scopeKey) {
          return current
        }

        return {
          ...current,
          data: patchNode(current.data, id, n => ({
            ...n,
            loading: false,
            error: error || undefined,
            children: error ? [] : entries.map(e => makeNode(e.path, e.name, e.isDirectory))
          }))
        }
      })
    },
    [connection, cwd, requestGateway, scopeKey]
  )

  useEffect(() => {
    void loadRoot(cwd, { connection, requestGateway })
  }, [connection, cwd, requestGateway, routeKey])

  const active = state.scopeKey === scopeKey

  return useMemo(
    () => ({
      collapseAll,
      collapseNonce: active ? state.collapseNonce : 0,
      data: active ? state.data : [],
      loadChildren,
      openState: active ? state.openState : {},
      refreshRoot,
      rootAvailability: active ? state.availability : 'healthy',
      rootError: active ? state.rootError : null,
      rootLoading: active ? state.rootLoading : Boolean(cwd),
      rootStale: active ? state.stale : false,
      rootTruncated: active ? state.truncated : false,
      setNodeOpen
    }),
    [
      active,
      collapseAll,
      cwd,
      loadChildren,
      refreshRoot,
      setNodeOpen,
      state.availability,
      state.collapseNonce,
      state.data,
      state.openState,
      state.rootError,
      state.rootLoading,
      state.stale,
      state.truncated
    ]
  )
}
