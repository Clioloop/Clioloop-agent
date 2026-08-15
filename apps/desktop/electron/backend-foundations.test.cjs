const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const {
  DESKTOP_IPC,
  backendRouteKey,
  createCrashJournal,
  createLivenessTracker,
  quitPromptFor
} = require('./backend-foundations.cjs')

test('CommonJS bridge preserves legacy local keys and typed IPC names', () => {
  assert.equal(backendRouteKey('local', ' author '), 'author')
  assert.equal(backendRouteKey('remote one', 'author'), 'connection:remote%20one::profile:author')
  assert.equal(DESKTOP_IPC.reviewDiff, 'clio:git-review:diff')
})

test('CommonJS liveness and quit guard policies are conservative', () => {
  const tracker = createLivenessTracker(2)
  assert.equal(tracker.record('remote', false, null, 1).state, 'degraded')
  assert.equal(tracker.record('remote', false, null, 2).state, 'offline')
  assert.match(quitPromptFor({ count: 1, titles: ['Deploy'] }).message, /^Clio /)
})

test('crash journal atomically records an unclean launch and clean quit', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'clio-crash-journal-'))
  try {
    const journal = createCrashJournal(path.join(root, 'journal.json'), { ...fs, dirname: path.dirname })
    journal.record('boot', { at: 1 })
    assert.deepEqual(journal.read(), { version: 1, at: 1, clean: false, phase: 'boot' })
    journal.record('quit', { at: 2 })
    assert.deepEqual(journal.read(), { version: 1, at: 2, clean: true, phase: 'quit' })
  } finally {
    fs.rmSync(root, { recursive: true, force: true })
  }
})
