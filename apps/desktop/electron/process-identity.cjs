const crypto = require('node:crypto')
const path = require('node:path')

const PURPOSE_RE = /^[a-z][a-z0-9_-]{0,31}$/

function canonicalInstallPath(root, platform = process.platform) {
  const resolved = path.resolve(String(root || ''))

  return platform === 'win32' ? resolved.toLowerCase() : resolved
}

function installId(root, platform = process.platform) {
  return crypto
    .createHash('sha256')
    .update(canonicalInstallPath(root, platform), 'utf8')
    .digest('hex')
    .slice(0, 12)
}

function processCreateTimeSeconds(nowMs = Date.now(), uptimeSeconds = process.uptime()) {
  const value = nowMs / 1000 - uptimeSeconds

  return Number.isFinite(value) && value > 0 ? value : null
}

function buildSpawnTag(purpose, root, options = {}) {
  if (!PURPOSE_RE.test(String(purpose || ''))) {
    throw new TypeError(`invalid Clio process purpose: ${purpose}`)
  }

  const pid = Number(options.pid ?? process.pid)
  const createTime = options.createTime ?? processCreateTimeSeconds()

  if (!Number.isInteger(pid) || pid <= 0) {
    throw new TypeError('invalid Clio spawner PID')
  }

  const createPart = Number.isFinite(createTime) && createTime > 0 ? Number(createTime).toFixed(3) : '-'

  return `v1:${installId(root, options.platform)}:${purpose}:${pid}:${createPart}`
}

module.exports = {
  buildSpawnTag,
  canonicalInstallPath,
  installId,
  processCreateTimeSeconds
}
