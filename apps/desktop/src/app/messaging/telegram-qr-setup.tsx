import QRCode from 'qrcode'
import { useCallback, useEffect, useRef, useState } from 'react'

import {
  applyTelegramOnboarding,
  cancelTelegramOnboarding,
  getActionStatus,
  getTelegramOnboardingStatus,
  restartGateway,
  startTelegramOnboarding,
  type TelegramOnboardingStart,
  testMessagingPlatform
} from '@/clio'
import { Button } from '@/components/ui/button'
import { Codicon } from '@/components/ui/codicon'
import { Input } from '@/components/ui/input'
import { notify } from '@/store/notifications'

const TELEGRAM_USER_ID_RE = /^\d{1,15}$/
const POLL_MS = 2000
const RESTART_POLL_MS = 1200
const RESTART_POLL_ATTEMPTS = 65
const CONNECTION_POLL_ATTEMPTS = 45

type Phase = 'applying' | 'connecting' | 'idle' | 'ready' | 'restart_failed' | 'starting' | 'waiting'

interface TelegramQrSetupProps {
  /** Called only after the gateway reports Telegram connected. */
  onApplied?: () => void
}

/**
 * One-scan Telegram bot setup for the desktop app — the same managed-bot QR
 * flow as the web dashboard. The customer scans the QR, Telegram creates their
 * own bot, and Clio saves the token locally and restarts the gateway.
 */
export function TelegramQrSetup({ onApplied }: TelegramQrSetupProps) {
  const [setup, setSetup] = useState<TelegramOnboardingStart | null>(null)
  const [qrDataUrl, setQrDataUrl] = useState('')
  const [phase, setPhase] = useState<Phase>('idle')
  const [botUsername, setBotUsername] = useState<null | string>(null)
  const [allowedIds, setAllowedIds] = useState<string[]>([])
  const [newAllowedId, setNewAllowedId] = useState('')
  const [error, setError] = useState('')
  const cancelledRef = useRef(false)

  const reset = useCallback(() => {
    setSetup(null)
    setQrDataUrl('')
    setPhase('idle')
    setBotUsername(null)
    setAllowedIds([])
    setNewAllowedId('')
    setError('')
  }, [])

  // Poll the pairing while waiting for the customer to create their bot.
  useEffect(() => {
    if (!setup || phase !== 'waiting') {return}
    cancelledRef.current = false
    let timer: null | ReturnType<typeof setTimeout> = null

    const poll = async () => {
      try {
        const status = await getTelegramOnboardingStatus(setup.pairing_id)

        if (cancelledRef.current) {return}

        if (status.status === 'ready') {
          setPhase('ready')
          setBotUsername(status.bot_username ?? null)
          setError('')

          if (status.owner_user_id && TELEGRAM_USER_ID_RE.test(status.owner_user_id)) {
            setAllowedIds([status.owner_user_id])
          }

          return
        }

        setError('')
        timer = setTimeout(poll, POLL_MS)
      } catch (err) {
        if (cancelledRef.current) {return}
        const expiresAt = Date.parse(setup.expires_at)

        if (Number.isFinite(expiresAt) && Date.now() >= expiresAt) {
          reset()
          setError('Telegram pairing expired. Start a new QR setup to try again.')

          return
        }

        timer = setTimeout(poll, POLL_MS)
      }
    }

    timer = setTimeout(poll, 1200)

    return () => {
      cancelledRef.current = true

      if (timer) {clearTimeout(timer)}
    }
  }, [phase, setup, reset])

  const start = useCallback(async () => {
    setPhase('starting')
    setError('')
    setBotUsername(null)
    setAllowedIds([])

    try {
      const res = await startTelegramOnboarding({ bot_name: 'Clioloop' })
      const dataUrl = await QRCode.toDataURL(res.qr_payload, { errorCorrectionLevel: 'M', margin: 1, width: 224 })
      setSetup(res)
      setQrDataUrl(dataUrl)
      setPhase('waiting')
    } catch (err) {
      setPhase('idle')
      setError(err instanceof Error ? err.message : String(err))
    }
  }, [])

  const cancel = useCallback(async () => {
    if (setup) {
      try {
        await cancelTelegramOnboarding(setup.pairing_id)
      } catch {
        /* local cleanup still wins */
      }
    }

    reset()
  }, [setup, reset])

  const addAllowedId = useCallback(() => {
    const trimmed = newAllowedId.trim()

    if (!TELEGRAM_USER_ID_RE.test(trimmed)) {
      setError('Allowed Telegram user IDs must be numeric.')

      return
    }

    setError('')
    setAllowedIds(ids => (ids.includes(trimmed) ? ids : [...ids, trimmed]))
    setNewAllowedId('')
  }, [newAllowedId])

  const restartAndVerify = useCallback(async () => {
    setPhase('connecting')
    setError('')

    try {
      const started = await restartGateway()
      let completed = false

      for (let attempt = 0; attempt < RESTART_POLL_ATTEMPTS; attempt += 1) {
        await new Promise(resolve => window.setTimeout(resolve, RESTART_POLL_MS))
        const status = await getActionStatus(started.name, 200)

        if (status.running) {continue}
        completed = true

        if (status.exit_code !== 0) {
          const detail = status.lines.filter(Boolean).slice(-6).join('\n')
          throw new Error(detail || `Gateway restart failed (exit ${String(status.exit_code)}).`)
        }

        break
      }

      if (!completed) {
        throw new Error('Gateway restart is taking too long. Check the gateway logs, then retry connection.')
      }

      let lastMessage = 'Telegram has not reported a connection yet.'

      for (let attempt = 0; attempt < CONNECTION_POLL_ATTEMPTS; attempt += 1) {
        const result = await testMessagingPlatform('telegram')
        lastMessage = result.message || lastMessage

        if (result.ok) {
          reset()
          notify({ kind: 'success', message: 'Telegram bot connected', title: 'Telegram' })
          onApplied?.()

          return
        }

        if (result.state === 'fatal') {
          throw new Error(lastMessage)
        }

        await new Promise(resolve => window.setTimeout(resolve, POLL_MS))
      }

      throw new Error(`${lastMessage} Retry the gateway connection.`)
    } catch (err) {
      setPhase('restart_failed')
      setError(err instanceof Error ? err.message : String(err))
    }
  }, [onApplied, reset])

  const apply = useCallback(async () => {
    if (!setup) {return}

    if (allowedIds.length === 0) {
      setError('Add at least one allowed Telegram user ID (yours).')

      return
    }

    setPhase('applying')
    setError('')

    try {
      await applyTelegramOnboarding(setup.pairing_id, { allowed_user_ids: allowedIds })
      await restartAndVerify()
    } catch (err) {
      setPhase('ready')
      setError(err instanceof Error ? err.message : String(err))
    }
  }, [setup, allowedIds, restartAndVerify])

  return (
    <div
      className="rounded-xl border border-(--ui-stroke-tertiary) bg-(--ui-bg-tertiary)/40 p-4"
      data-testid="telegram-qr-setup"
    >
      <div className="flex items-center gap-2">
        <Codicon className="text-(--ui-accent)" name="device-mobile" size="1rem" />
        <h4 className="text-[0.875rem] font-semibold">Quick setup with QR</h4>
      </div>
      <p className="mt-1 text-[length:var(--conversation-caption-font-size)] text-(--ui-text-tertiary)">
        Scan a code with Telegram to create your own bot automatically — no BotFather token copy-paste.
      </p>

      {error && <p className="mt-2 text-[0.8125rem] text-destructive">{error}</p>}

      {phase === 'idle' && (
        <Button className="mt-3" disabled={false} onClick={() => void start()} size="sm">
          Set up with QR
        </Button>
      )}

      {phase === 'starting' && (
        <p className="mt-3 text-[0.8125rem] text-(--ui-text-secondary)">Preparing Telegram support…</p>
      )}

      {phase === 'connecting' && (
        <p className="mt-3 text-[0.8125rem] text-(--ui-text-secondary)">
          Restarting the gateway and verifying Telegram…
        </p>
      )}

      {phase === 'restart_failed' && (
        <div className="mt-3 flex items-center gap-2">
          <Button onClick={() => void restartAndVerify()} size="sm">
            Retry gateway connection
          </Button>
          <Button onClick={reset} size="sm" variant="ghost">
            Close
          </Button>
        </div>
      )}

      {(phase === 'waiting' || phase === 'starting') && qrDataUrl && (
        <div className="mt-3 flex flex-col items-center gap-2">
          <img alt="Telegram setup QR code" className="rounded-lg bg-white p-2" height={224} src={qrDataUrl} width={224} />
          <p className="text-center text-[0.75rem] text-(--ui-text-tertiary)">
            Scan with your phone, or{' '}
            {setup && (
              <a className="text-(--ui-accent) underline" href={setup.deep_link} rel="noreferrer" target="_blank">
                open in Telegram
              </a>
            )}
            . Tap “Create Bot” to confirm.
          </p>
          <Button onClick={() => void cancel()} size="sm" variant="ghost">
            Cancel
          </Button>
        </div>
      )}

      {(phase === 'ready' || phase === 'applying') && (
        <div className="mt-3 space-y-3">
          <p className="text-[0.8125rem] text-emerald-500">
            ✓ Bot created{botUsername ? `: @${botUsername}` : ''}. Now allow your Telegram account to use it.
          </p>
          <div>
            <p className="mb-1 text-[0.75rem] text-(--ui-text-tertiary)">
              Allowed Telegram user IDs (only these accounts can DM the bot):
            </p>
            <div className="flex flex-wrap gap-1.5">
              {allowedIds.map(id => (
                <span
                  className="inline-flex items-center gap-1 rounded-full bg-(--ui-bg-quaternary) px-2 py-0.5 text-[0.75rem]"
                  key={id}
                >
                  {id}
                  <button
                    aria-label={`Remove ${id}`}
                    className="text-(--ui-text-tertiary) hover:text-foreground"
                    onClick={() => setAllowedIds(ids => ids.filter(x => x !== id))}
                    type="button"
                  >
                    <Codicon name="close" size="0.75rem" />
                  </button>
                </span>
              ))}
            </div>
            <div className="mt-2 flex gap-2">
              <Input
                aria-label="Telegram user ID"
                className="max-w-[12rem]"
                onChange={e => setNewAllowedId(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter') {addAllowedId()}
                }}
                placeholder="123456789"
                value={newAllowedId}
              />
              <Button disabled={!newAllowedId.trim()} onClick={addAllowedId} size="sm" variant="outline">
                Add
              </Button>
            </div>
            <p className="mt-1 text-[0.6875rem] text-(--ui-text-quaternary)">
              Not sure? DM <span className="font-medium">@userinfobot</span> on Telegram to get your numeric ID.
            </p>
          </div>
          <div className="flex gap-2">
            <Button disabled={phase === 'applying' || allowedIds.length === 0} onClick={() => void apply()} size="sm">
              {phase === 'applying' ? 'Saving…' : 'Save & restart gateway'}
            </Button>
            <Button onClick={() => void cancel()} size="sm" variant="ghost">
              Cancel
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

export { TELEGRAM_USER_ID_RE }
