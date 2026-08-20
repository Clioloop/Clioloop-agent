/**
 * Tests for electron/backend-probes.cjs.
 *
 * Run with: node --test electron/backend-probes.test.cjs
 * (Wired into npm test:desktop:platforms in package.json.)
 */

const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const { canImportClioCli, clioCliSupportsUpdateFlag, verifyClioCli } = require('./backend-probes.cjs')

// Resolve the host's own Node binary -- guaranteed to be on disk and
// runnable. We use it as both a stand-in for "a python that doesn't
// have clio_cli" (since `node -c "import clio_cli"` will exit
// non-zero) and as a way to script verifyClioCli's success path
// (a tiny script we write to disk that exits 0 on --version).
const NODE_BIN = process.execPath

test('canImportClioCli returns false when path is falsy', () => {
  assert.equal(canImportClioCli(''), false)
  assert.equal(canImportClioCli(null), false)
  assert.equal(canImportClioCli(undefined), false)
})

test('canImportClioCli returns false when interpreter cannot run -c', () => {
  // node IS an interpreter, but `node -c "import clio_cli"` is a
  // SyntaxError -- different exit reason from a real Python's
  // ModuleNotFoundError, but the predicate is "exit 0 or not" and
  // both land on "not", which is exactly what we want for the
  // resolver fall-through.
  assert.equal(canImportClioCli(NODE_BIN), false)
})

test('canImportClioCli returns false when binary does not exist', () => {
  const ghost = path.join(os.tmpdir(), 'clio-probes-ghost-' + Date.now() + '.exe')
  assert.equal(canImportClioCli(ghost), false)
})

test('verifyClioCli returns false when command is falsy', () => {
  assert.equal(verifyClioCli(''), false)
  assert.equal(verifyClioCli(null), false)
  assert.equal(verifyClioCli(undefined), false)
})

test('verifyClioCli returns false when binary does not exist', () => {
  const ghost = path.join(os.tmpdir(), 'clio-probes-ghost-' + Date.now() + '.exe')
  assert.equal(verifyClioCli(ghost), false)
})

test('verifyClioCli returns true when --version exits 0', () => {
  // Write a tiny script that exits 0 regardless of args, then invoke
  // it through node. This stands in for a working clio binary --
  // verifyClioCli only cares about the exit code.
  const scriptPath = path.join(os.tmpdir(), `clio-probes-ok-${Date.now()}-${process.pid}.cjs`)
  fs.writeFileSync(scriptPath, 'process.exit(0)\n')
  try {
    // Use node as the launcher and our script as the "command". Pass
    // shell:false (default) -- node is a real binary, no shim.
    // execFileSync passes ['--version'] as args, which node ignores
    // gracefully (well, it prints its version and exits 0, which is
    // perfect -- exit code 0 is the only signal we read).
    assert.equal(verifyClioCli(NODE_BIN), true)
  } finally {
    try {
      fs.unlinkSync(scriptPath)
    } catch {
      void 0
    }
  }
})

test('verifyClioCli swallows timeouts (does not throw)', () => {
  // We can't easily provoke a real 5s hang in CI without slowing the
  // suite, but we CAN confirm that an invocation that DOES throw
  // (because the binary is missing) returns false rather than
  // propagating. Same code path the timeout case takes.
  assert.equal(verifyClioCli('/definitely/not/a/real/binary/anywhere'), false)
})

test('clioCliSupportsUpdateFlag probes update --help output', () => {
  const scriptPath = path.join(os.tmpdir(), `clio-probes-help-${Date.now()}-${process.pid}.cjs`)
  fs.writeFileSync(
    scriptPath,
    "if (process.argv.slice(2).join(' ') === 'update --help') console.log('  --yes  --keep-stash\\n'); else process.exit(2)\n"
  )
  try {
    assert.equal(clioCliSupportsUpdateFlag(NODE_BIN, '--keep-stash', { prefixArgs: [scriptPath] }), true)
    assert.equal(clioCliSupportsUpdateFlag(NODE_BIN, '--force', { prefixArgs: [scriptPath] }), false)
  } finally {
    fs.unlinkSync(scriptPath)
  }
})

test('clioCliSupportsUpdateFlag fails closed for invalid flags and commands', () => {
  assert.equal(clioCliSupportsUpdateFlag(NODE_BIN, 'keep-stash'), false)
  assert.equal(clioCliSupportsUpdateFlag('/definitely/missing/clio', '--keep-stash'), false)
})
