'use strict'

/**
 * Runtime bridge for the typed policies in src/desktop/backend-foundations.ts.
 * Keep this dependency-free: main.cjs and preload.cjs can require it before
 * Electron is ready, while renderer code consumes the TypeScript contracts.
 */

const LOCAL_CONNECTION_ID = 'local'
const DESKTOP_IPC = Object.freeze({
  projectsList: 'clio:projects:list',
  projectAdd: 'clio:projects:add',
  worktreesList: 'clio:worktrees:list',
  worktreeCreate: 'clio:worktrees:create',
  worktreeRemove: 'clio:worktrees:remove',
  reviewList: 'clio:git-review:list',
  reviewDiff: 'clio:git-review:diff',
  reviewStage: 'clio:git-review:stage',
  reviewCommit: 'clio:git-review:commit'
})

function profileRouteKey(profile) {
  return String(profile ?? '').trim() || 'default'
}

function backendRouteKey(connectionId, profile) {
  const profileKey = profileRouteKey(profile)
  const connectionKey = String(connectionId ?? '').trim()
  return !connectionKey || connectionKey === LOCAL_CONNECTION_ID
    ? profileKey
    : `connection:${encodeURIComponent(connectionKey)}::profile:${encodeURIComponent(profileKey)}`
}

function createLivenessTracker(failureLimit = 3) {
  if (!Number.isInteger(failureLimit) || failureLimit < 1) {
    throw new Error('failureLimit must be a positive integer')
  }
  const routes = new Map()
  return {
    record(routeKey, ok, latencyMs, checkedAt = Date.now()) {
      const previous = routes.get(routeKey)
      const failures = ok ? 0 : (previous?.failures ?? 0) + 1
      const state = ok ? 'healthy' : failures >= failureLimit ? 'offline' : 'degraded'
      const observation = { checkedAt, failures, latencyMs: ok ? latencyMs : null, state }
      routes.set(routeKey, observation)
      return observation
    },
    get(routeKey) {
      return routes.get(routeKey) ?? null
    },
    clear(routeKey) {
      if (routeKey) routes.delete(routeKey)
      else routes.clear()
    }
  }
}

function normalizeActiveWork(value) {
  if (!value || typeof value !== 'object') return { count: 0, titles: [] }
  const titles = Array.isArray(value.titles)
    ? [...new Set(value.titles.filter(title => typeof title === 'string').map(title => title.trim()).filter(Boolean))]
    : []
  const count = typeof value.count === 'number' && Number.isFinite(value.count)
    ? Math.max(0, Math.floor(value.count))
    : 0
  return { count: Math.max(count, titles.length), titles }
}

function quitPromptFor(work, handoff = false) {
  if (handoff || work.count === 0) return null
  const listed = work.titles.slice(0, 4)
  const remaining = work.count - listed.length
  const lines = listed.map(title => `• ${title}`)
  if (remaining > 0) lines.push(`• ${remaining} more`)
  return {
    message: `Clio is still working on ${work.count} ${work.count === 1 ? 'chat' : 'chats'}.`,
    detail: `${lines.length ? `${lines.join('\n')}\n\n` : ''}Quitting stops active work and may leave a tool operation incomplete.`
  }
}

function nextCrashJournalEntry(phase, options = {}) {
  const rawReason = options.reason instanceof Error
    ? options.reason.stack || options.reason.message
    : String(options.reason ?? '').trim()
  return {
    version: 1,
    at: options.at ?? Date.now(),
    clean: options.clean ?? phase === 'quit',
    phase,
    ...(rawReason ? { reason: rawReason.slice(0, 8192) } : {})
  }
}

/** Atomic journal adapter. fs/path are injected to keep the primitive testable. */
function createCrashJournal(filePath, io) {
  const tempPath = `${filePath}.tmp`
  const write = entry => {
    io.mkdirSync(io.dirname(filePath), { recursive: true })
    io.writeFileSync(tempPath, `${JSON.stringify(entry)}\n`, { encoding: 'utf8', mode: 0o600 })
    io.renameSync(tempPath, filePath)
    return entry
  }
  return {
    read() {
      try {
        const value = JSON.parse(io.readFileSync(filePath, 'utf8'))
        return value && value.version === 1 ? value : null
      } catch {
        return null
      }
    },
    record(phase, options) {
      return write(nextCrashJournalEntry(phase, options))
    }
  }
}

module.exports = {
  DESKTOP_IPC,
  LOCAL_CONNECTION_ID,
  backendRouteKey,
  createCrashJournal,
  createLivenessTracker,
  nextCrashJournalEntry,
  normalizeActiveWork,
  profileRouteKey,
  quitPromptFor
}
