const assert = require('node:assert/strict')
const test = require('node:test')

const {
  buildSpawnTag,
  canonicalInstallPath,
  installId,
  processCreateTimeSeconds,
  windowsProcessCreateTimeSeconds,
  WINDOWS_CREATE_TIME_TIMEOUT_MS
} = require('./process-identity.cjs')

test('spawn tag matches the Python v1 identity contract', () => {
  const root = process.platform === 'win32' ? 'C:\\Clio\\Agent' : '/opt/clio-agent'
  const tag = buildSpawnTag('dashboard', root, {
    createTime: 1234.56789,
    pid: 42,
    platform: process.platform
  })

  assert.equal(tag, `v1:${installId(root)}:dashboard:42:1234.568`)
})

test('Windows install identity is case-insensitive', () => {
  assert.equal(canonicalInstallPath('C:\\Clio\\Agent', 'win32'), canonicalInstallPath('c:\\clio\\agent', 'win32'))
  assert.equal(installId('C:\\Clio\\Agent', 'win32'), installId('c:\\clio\\agent', 'win32'))
})

test('POSIX create time keeps deriving an epoch timestamp from uptime', () => {
  assert.equal(processCreateTimeSeconds(10_000, 2.5), 7.5)
})

test('Windows create time prefers Electron native process metadata', () => {
  let queried = false
  const seconds = windowsProcessCreateTimeSeconds(42, {
    electronCreationTime: 1_234_567,
    execFileSync: () => {
      queried = true
      throw new Error('PowerShell should not run')
    }
  })

  assert.equal(seconds, 1234.567)
  assert.equal(queried, false)
})

test('Windows create time uses a bounded Get-Process query when Electron metadata is unavailable', () => {
  const expectedMilliseconds = 1_725_000_123_456n
  const ticks = 621355968000000000n + expectedMilliseconds * 10_000n
  let call

  const seconds = windowsProcessCreateTimeSeconds(42, {
    electronCreationTime: null,
    execFileSync: (command, args, options) => {
      call = { args, command, options }
      return `${ticks}\r\n`
    }
  })

  assert.equal(seconds, Number(expectedMilliseconds) / 1000)
  assert.equal(call.command, 'powershell.exe')
  assert.ok(call.args.includes('-NoProfile'))
  assert.match(call.args.at(-1), /Get-Process -Id 42/)
  assert.equal(call.options.timeout, WINDOWS_CREATE_TIME_TIMEOUT_MS)
  assert.ok(call.options.timeout > 0)
  assert.equal(call.options.windowsHide, true)
})

test('Windows spawn tags emit unknown create time when the native query is unavailable', () => {
  const tag = buildSpawnTag('dashboard', 'C:\\Clio\\Agent', {
    electronCreationTime: null,
    execFileSync: () => {
      throw new Error('PowerShell unavailable')
    },
    pid: 42,
    platform: 'win32'
  })

  assert.match(tag, /:dashboard:42:-$/)
})

test('invalid process purposes and PIDs fail closed without invoking PowerShell', () => {
  let queried = false

  assert.throws(() => buildSpawnTag('../bad', '/tmp/clio', { createTime: 1, pid: 1 }), /invalid/)
  assert.throws(() => buildSpawnTag('dashboard', '/tmp/clio', { createTime: 1, pid: 0 }), /PID/)
  assert.equal(
    windowsProcessCreateTimeSeconds('42; exit 0', {
      execFileSync: () => {
        queried = true
      }
    }),
    null
  )
  assert.equal(queried, false)
})
