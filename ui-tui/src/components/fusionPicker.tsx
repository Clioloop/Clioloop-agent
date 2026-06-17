import { Box, Text, useInput, useStdout } from '@clio/ink'
import { useEffect, useMemo, useState } from 'react'

import type { GatewayClient } from '../gatewayClient.js'
import type { ModelOptionsResponse, SlashExecResponse } from '../gatewayTypes.js'
import { fuzzyRank } from '../lib/fuzzy.js'
import { asRpcResult, rpcErrorMessage } from '../lib/rpc.js'
import type { Theme } from '../theme.js'

import { OverlayHint, windowItems } from './overlayControls.js'

const COUNTS = [1, 2, 3, 4, 5]
const VISIBLE = 10
const MIN_WIDTH = 44
const MAX_WIDTH = 92

type Phase = 'plannerCount' | 'plannerPick' | 'reviewerCount' | 'reviewerPick' | 'submitting' | 'done'

export function FusionPicker({ gw, onCancel, onNotice, sessionId, t }: FusionPickerProps) {
  const [models, setModels] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const [phase, setPhase] = useState<Phase>('plannerCount')
  const [idx, setIdx] = useState(0)
  const [filter, setFilter] = useState('')
  const [plannerCount, setPlannerCount] = useState(0)
  const [reviewerCount, setReviewerCount] = useState(0)
  const [advisors, setAdvisors] = useState<string[]>([])
  const [reviewers, setReviewers] = useState<string[]>([])
  const [notice, setNotice] = useState('')
  const { stdout } = useStdout()
  const width = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, (stdout?.columns ?? 80) - 6))

  useEffect(() => {
    gw.request<ModelOptionsResponse>('model.options', sessionId ? { session_id: sessionId } : {})
      .then(raw => {
        const r = asRpcResult<ModelOptionsResponse>(raw)
        const managed = (r?.providers ?? []).find(p => p.slug === 'managed')
        const listed = managed?.models ?? []
        const open = listed.filter(m => !m.includes('/')).sort()
        const routed = listed.filter(m => m.includes('/')).sort()

        setModels([...open, ...routed])
        setLoading(false)
        setErr(managed ? '' : 'managed portal models are unavailable')
      })
      .catch((e: unknown) => {
        setErr(rpcErrorMessage(e))
        setLoading(false)
      })
  }, [gw, sessionId])

  const filteredModels = useMemo(
    () => (filter.trim() ? fuzzyRank(models, filter, m => m).map(r => r.item) : models),
    [models, filter]
  )

  useEffect(() => {
    if (idx >= filteredModels.length && filteredModels.length > 0) {
      setIdx(0)
    }
  }, [filteredModels.length, idx])

  const title =
    phase === 'plannerCount'
      ? 'How many planner models?'
      : phase === 'plannerPick'
        ? `Pick planner ${advisors.length + 1} of ${plannerCount}`
        : phase === 'reviewerCount'
          ? 'How many reviewer models?'
          : phase === 'reviewerPick'
            ? `Pick reviewer ${reviewers.length + 1} of ${reviewerCount}`
            : phase === 'submitting'
              ? 'Configuring Fusion...'
              : 'Fusion configured'

  const submit = (selectedReviewers: string[]) => {
    if (!sessionId) {
      setErr('session not ready yet')
      setPhase('reviewerPick')

      return
    }

    setPhase('submitting')
    const command = `fusion advisors=${advisors.join(',')} reviewers=${selectedReviewers.join(',')}`

    gw.request<SlashExecResponse>('slash.exec', { command, session_id: sessionId })
      .then(raw => {
        const r = asRpcResult<SlashExecResponse>(raw)
        const output = r?.output?.replace(/\*/g, '') || 'Fusion configured.'

        setNotice(output)
        setPhase('done')
        onNotice(output)
      })
      .catch((e: unknown) => {
        setErr(rpcErrorMessage(e))
        setPhase('reviewerPick')
      })
  }

  const selectModel = (model: string) => {
    setFilter('')
    setIdx(0)

    if (phase === 'plannerPick') {
      const next = [...advisors, model]
      setAdvisors(next)
      if (next.length >= plannerCount) {
        setPhase('reviewerCount')
      }

      return
    }

    if (phase === 'reviewerPick') {
      const next = [...reviewers, model]
      setReviewers(next)
      if (next.length >= reviewerCount) {
        submit(next)
      }
    }
  }

  const back = () => {
    if ((phase === 'plannerPick' || phase === 'reviewerPick') && filter.trim()) {
      setFilter('')
      setIdx(0)

      return
    }

    if (phase === 'done') {
      onCancel()

      return
    }

    if (phase === 'reviewerPick') {
      if (reviewers.length) {
        setReviewers(v => v.slice(0, -1))
      } else {
        setPhase('reviewerCount')
      }

      return
    }

    if (phase === 'reviewerCount') {
      setAdvisors(v => v.slice(0, -1))
      setPhase('plannerPick')

      return
    }

    if (phase === 'plannerPick') {
      if (advisors.length) {
        setAdvisors(v => v.slice(0, -1))
      } else {
        setPhase('plannerCount')
      }

      return
    }

    onCancel()
  }

  useInput((ch, key) => {
    if (phase === 'submitting') {
      return
    }

    if (key.escape) {
      back()

      return
    }

    if (ch === 'q' && !filter) {
      onCancel()

      return
    }

    if (phase === 'done') {
      if (key.return) {
        onCancel()
      }

      return
    }

    if (phase === 'plannerCount' || phase === 'reviewerCount') {
      const n = Number(ch)
      if (COUNTS.includes(n)) {
        if (phase === 'plannerCount') {
          setPlannerCount(n)
          setPhase('plannerPick')
        } else {
          setReviewerCount(n)
          setPhase('reviewerPick')
        }
        setIdx(0)
      }

      return
    }

    if (key.upArrow && idx > 0) {
      setIdx(v => v - 1)

      return
    }

    if (key.downArrow && idx < filteredModels.length - 1) {
      setIdx(v => v + 1)

      return
    }

    if (key.return) {
      const model = filteredModels[idx]
      if (model) {
        selectModel(model)
      }

      return
    }

    if (key.backspace || key.delete) {
      setFilter(v => v.slice(0, -1))
      setIdx(0)

      return
    }

    if (ch === '\u0015') {
      setFilter('')
      setIdx(0)

      return
    }

    if (ch && !key.ctrl && !key.meta) {
      setFilter(v => v + ch)
      setIdx(0)
    }
  })

  const isCount = phase === 'plannerCount' || phase === 'reviewerCount'
  const { items, offset } = windowItems(filteredModels, idx, VISIBLE)

  return (
    <Box flexDirection="column" paddingX={1} paddingY={1} width={width}>
      <Box justifyContent="center" marginBottom={1}>
        <Text bold color={t.color.primary}>
          Fusion
        </Text>
      </Box>

      <Text color={t.color.label} wrap="truncate-end">{title}</Text>
      {!!advisors.length && <Text color={t.color.muted} wrap="truncate-end">planners: {advisors.join(' · ')}</Text>}
      {!!reviewers.length && <Text color={t.color.muted} wrap="truncate-end">reviewers: {reviewers.join(' · ')}</Text>}

      {loading ? (
        <Text color={t.color.muted}>loading managed models...</Text>
      ) : err ? (
        <Text color={t.color.error}>{err}</Text>
      ) : isCount ? (
        <Box flexDirection="column" marginTop={1}>
          <Text color={t.color.muted}>press 1-5</Text>
          <Text color={t.color.accent}>{COUNTS.join('  ')}</Text>
        </Box>
      ) : phase === 'done' ? (
        <Box flexDirection="column" marginTop={1}>
          <Text color={t.color.text} wrap="wrap">{notice || 'Fusion configured.'}</Text>
          <OverlayHint t={t}>Enter/Esc/q close</OverlayHint>
        </Box>
      ) : (
        <Box flexDirection="column" marginTop={1}>
          {filter ? <Text color={t.color.muted}>filter: {filter}</Text> : <Text color={t.color.muted}>type to filter</Text>}
          {items.map((model, i) => {
            const absolute = offset + i
            const active = absolute === idx
            const tag = model.includes('/') ? ' · openrouter' : ' · open'

            return (
              <Text
                bold={active}
                color={active ? t.color.accent : t.color.muted}
                inverse={active}
                key={`${absolute}:${model}`}
                wrap="truncate-end"
              >
                {active ? '▸ ' : '  '}
                {absolute + 1}. {model}
                {tag}
              </Text>
            )
          })}
          {!items.length && <Text color={t.color.muted}>no models match</Text>}
          <Text color={t.color.muted} wrap="truncate-end">
            {offset + VISIBLE < filteredModels.length ? ` ↓ ${filteredModels.length - offset - VISIBLE} more` : ' '}
          </Text>
        </Box>
      )}

      {phase !== 'done' && (
        <OverlayHint t={t}>
          {isCount ? '1-5 choose · Esc/back · q close' : '↑/↓ select · Enter choose · Esc back · q close'}
        </OverlayHint>
      )}
    </Box>
  )
}

interface FusionPickerProps {
  gw: GatewayClient
  onCancel: () => void
  onNotice: (text: string) => void
  sessionId: string | null
  t: Theme
}
