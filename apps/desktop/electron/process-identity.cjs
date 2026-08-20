const crypto = require('node:crypto')
const { execFileSync } = require('node:child_process')
const path = require('node:path')

const PURPOSE_RE = /^[a-z][a-z0-9_-]{0,31}$/
const WINDOWS_CREATE_TIME_TIMEOUT_MS = 10_000
const WINDOWS_EPOCH_TICKS = 621355968000000000n

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

/**
 * Query the Windows process creation time instead of estimating it from the
 * wall clock. Wall-clock adjustments make Date.now() - process.uptime() an
 * unsafe PID-reuse identity on Windows.
 *
 * Electron exposes the same native value for its own process. PowerShell is a
 * bounded fallback for runtimes where that API is absent. Any missing,
 * malformed, failed, or timed-out query returns null so the spawn tag emits
 * '-' and downstream ownership checks fail closed.
 */
function windowsProcessCreateTimeSeconds(pid, options = {}) {
  // Keep the value interpolated into the PowerShell program strictly numeric,
  // including when this exported helper is called outside buildSpawnTag.
  if (!Number.isInteger(pid) || pid <= 0) {
    return null
  }

  const hasElectronCreationTime = Object.prototype.hasOwnProperty.call(options, 'electronCreationTime')
  let electronCreationTime = hasElectronCreationTime ? options.electronCreationTime : null

  if (!hasElectronCreationTime && pid === process.pid && typeof process.getCreationTime === 'function') {
    try {
      electronCreationTime = process.getCreationTime()
    } catch {
      electronCreationTime = null
    }
  }

  if (Number.isFinite(electronCreationTime) && electronCreationTime > 0) {
    return Number(electronCreationTime) / 1000
  }

  const query = options.execFileSync || execFileSync

  try {
    const raw = String(
      query(
        'powershell.exe',
        [
          '-NoProfile',
          '-NonInteractive',
          '-Command',
          `$p = Get-Process -Id ${pid} -ErrorAction Stop; [Console]::Out.Write($p.StartTime.ToUniversalTime().Ticks)`
        ],
        {
          encoding: 'utf8',
          stdio: ['ignore', 'pipe', 'ignore'],
          timeout: WINDOWS_CREATE_TIME_TIMEOUT_MS,
          windowsHide: true
        }
      ) || ''
    ).trim()

    if (!/^\d+$/.test(raw)) {
      return null
    }

    const milliseconds = (BigInt(raw) - WINDOWS_EPOCH_TICKS) / 10_000n
    const seconds = Number(milliseconds) / 1000

    return Number.isFinite(seconds) && seconds > 0 ? seconds : null
  } catch {
    return null
  }
}

function buildSpawnTag(purpose, root, options = {}) {
  if (!PURPOSE_RE.test(String(purpose || ''))) {
    throw new TypeError(`invalid Clio process purpose: ${purpose}`)
  }

  const pid = Number(options.pid ?? process.pid)
  const platform = options.platform ?? process.platform

  if (!Number.isInteger(pid) || pid <= 0) {
    throw new TypeError('invalid Clio spawner PID')
  }

  const createTime = Object.prototype.hasOwnProperty.call(options, 'createTime')
    ? options.createTime
    : platform === 'win32'
      ? windowsProcessCreateTimeSeconds(pid, options)
      : processCreateTimeSeconds()

  const createPart = Number.isFinite(createTime) && createTime > 0 ? Number(createTime).toFixed(3) : '-'

  return `v1:${installId(root, platform)}:${purpose}:${pid}:${createPart}`
}

module.exports = {
  buildSpawnTag,
  canonicalInstallPath,
  installId,
  processCreateTimeSeconds,
  windowsProcessCreateTimeSeconds,
  WINDOWS_CREATE_TIME_TIMEOUT_MS
}
