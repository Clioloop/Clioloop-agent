const assert = require('node:assert/strict')
const test = require('node:test')

const {
  buildSpawnTag,
  canonicalInstallPath,
  installId,
  processCreateTimeSeconds
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

test('create time derives an epoch timestamp from uptime', () => {
  assert.equal(processCreateTimeSeconds(10_000, 2.5), 7.5)
})

test('invalid process purposes and PIDs fail closed', () => {
  assert.throws(() => buildSpawnTag('../bad', '/tmp/clio', { createTime: 1, pid: 1 }), /invalid/)
  assert.throws(() => buildSpawnTag('dashboard', '/tmp/clio', { createTime: 1, pid: 0 }), /PID/)
})
