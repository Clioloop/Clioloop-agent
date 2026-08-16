import { useStore } from '@nanostores/react'
import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'

import type { ClioGateway } from '@/clio'
import { getGlobalModelOptions } from '@/clio'
import { Button } from '@/components/ui/button'
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList
} from '@/components/ui/command'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog'
import { managedModelTag } from '@/lib/model-tag'
import { OMNI_PROVIDER_LABEL, OMNI_PROVIDER_SLUG } from '@/lib/provider-label'
import { notify, notifyError } from '@/store/notifications'
import { $activeSessionId, $fusionPickerOpen, $gatewayState, setFusionPickerOpen } from '@/store/session'
import type { ModelOptionProvider, ModelOptionsResponse, ModelPricing } from '@/types/clio'

const MAX_PER_GROUP = 5
const COUNTS = [1, 2, 3, 4, 5]

type Phase = 'plannerCount' | 'plannerPick' | 'reviewerCount' | 'reviewerPick' | 'submitting'

/** Store-driven mount, mirroring ModelPickerOverlay. */
export function FusionSetupOverlay({ gateway }: { gateway?: ClioGateway }) {
  const open = useStore($fusionPickerOpen)
  const sessionId = useStore($activeSessionId)
  const gatewayOpen = useStore($gatewayState) === 'open'

  if (!gatewayOpen) {
    return null
  }

  return <FusionSetupDialog gw={gateway} onOpenChange={setFusionPickerOpen} open={open} sessionId={sessionId} />
}

function FusionSetupDialog({
  open,
  onOpenChange,
  gw,
  sessionId
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  gw?: ClioGateway
  sessionId: string | null
}) {
  const [phase, setPhase] = useState<Phase>('plannerCount')
  const [plannerCount, setPlannerCount] = useState(0)
  const [advisors, setAdvisors] = useState<string[]>([])
  const [reviewerCount, setReviewerCount] = useState(0)
  const [reviewers, setReviewers] = useState<string[]>([])
  const [search, setSearch] = useState('')

  // Reset the wizard each time it opens.
  useEffect(() => {
    if (open) {
      setPhase('plannerCount')
      setPlannerCount(0)
      setAdvisors([])
      setReviewerCount(0)
      setReviewers([])
      setSearch('')
    }
  }, [open])

  const modelOptions = useQuery({
    queryKey: ['model-options', sessionId || 'global'],
    queryFn: () =>
      gw && sessionId
        ? gw.request<ModelOptionsResponse>('model.options', { session_id: sessionId })
        : getGlobalModelOptions(),
    enabled: open
  })

  const managed: ModelOptionProvider | undefined = useMemo(
    () => (modelOptions.data?.providers ?? []).find(p => p.slug === OMNI_PROVIDER_SLUG),
    [modelOptions.data]
  )

  const models = managed?.models ?? []
  const pricing = managed?.pricing ?? {}
  const warnings = managed?.model_warnings ?? {}
  const loading = modelOptions.isPending && !modelOptions.data

  const submit = async (selectedReviewers = reviewers) => {
    if (!gw || !sessionId) {
      notifyError(new Error('Open a chat first, then run /fusion.'), 'Fusion')

      return
    }

    setPhase('submitting')
    const command = `fusion advisors=${advisors.join(',')} reviewers=${selectedReviewers.join(',')}`

    try {
      const res = await gw.request<{ output?: string; warning?: string }>('slash.exec', {
        session_id: sessionId,
        command
      })

      notify({ kind: 'success', title: 'Fusion', message: res?.output?.replace(/\*/g, '') || 'Fusion configured.' })
      onOpenChange(false)
    } catch (err) {
      setPhase('reviewerPick')
      notifyError(err, 'Could not configure Fusion')
    }
  }

  // A model click advances the wizard through its phases.
  const pickModel = (model: string) => {
    setSearch('')

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
        void submit(next)
      }

      return
    }
  }

  const pickCount = (n: number) => {
    const count = Math.max(1, Math.min(MAX_PER_GROUP, n))
    setSearch('')

    if (phase === 'plannerCount') {
      setPlannerCount(count)
      setPhase('plannerPick')
    } else if (phase === 'reviewerCount') {
      setReviewerCount(count)
      setPhase('reviewerPick')
    }
  }

  const back = () => {
    setSearch('')

    switch (phase) {
      case 'reviewerPick':
        if (reviewers.length > 0) {
          setReviewers(r => r.slice(0, -1))
        } else {
          setPhase('reviewerCount')
        }

        break

      case 'reviewerCount':
        setAdvisors(a => a.slice(0, -1))
        setPhase('plannerPick')

        break

      case 'plannerPick':
        if (advisors.length > 0) {
          setAdvisors(a => a.slice(0, -1))
        } else {
          setPhase('plannerCount')
        }

        break

      default:
        break
    }
  }

  const isCountPhase = phase === 'plannerCount' || phase === 'reviewerCount'

  const title =
    phase === 'plannerCount'
      ? 'How many models should plan the task? (1–5)'
      : phase === 'plannerPick'
        ? `Pick planner model ${advisors.length + 1} of ${plannerCount}`
        : phase === 'reviewerCount'
          ? 'How many models should review the draft? (1–5)'
          : phase === 'reviewerPick'
            ? `Pick reviewer model ${reviewers.length + 1} of ${reviewerCount}`
            : 'Configuring Fusion…'

  const q = search.trim().toLowerCase()
  const visibleModels = q ? models.filter(m => m.toLowerCase().includes(q)) : models

  return (
    <Dialog onOpenChange={onOpenChange} open={open}>
      <DialogContent className="max-h-[85vh] max-w-2xl gap-0 overflow-hidden p-0">
        <DialogHeader className="border-b border-border px-4 py-3">
          <DialogTitle>🔮 Model Fusion</DialogTitle>
          <DialogDescription className="font-mono text-xs leading-relaxed">
            {title}
            {advisors.length > 0 && <span className="block opacity-80">planners: {advisors.join(' · ')}</span>}
            {reviewers.length > 0 && <span className="block opacity-80">reviewers: {reviewers.join(' · ')}</span>}
          </DialogDescription>
        </DialogHeader>

        {modelOptions.error ? (
          <div className="px-4 py-6 text-sm text-destructive">Could not load models.</div>
        ) : !managed && !loading ? (
          <div className="px-4 py-6 text-sm text-muted-foreground">
            Fusion needs {OMNI_PROVIDER_LABEL} (Pro plan or higher). Connect it first.
          </div>
        ) : isCountPhase ? (
          <div className="flex flex-wrap gap-2 p-4">
            {COUNTS.map(n => (
              <Button key={n} onClick={() => pickCount(n)} variant="outline">
                {n}
              </Button>
            ))}
          </div>
        ) : phase === 'submitting' ? (
          <div className="px-4 py-6 text-sm text-muted-foreground">Configuring Fusion…</div>
        ) : (
          <Command className="rounded-none bg-card" shouldFilter={false}>
            <CommandInput
              autoFocus
              onValueChange={setSearch}
              placeholder="Filter models…"
              value={search}
            />
            <CommandList className="max-h-96">
              {!loading && <CommandEmpty>No models found.</CommandEmpty>}
              <CommandGroup>
                {visibleModels.map(model => {
                  const price: ModelPricing | undefined = pricing[model]
                  const warning = warnings[model]

                  return (
                    <CommandItem
                      className="flex items-center gap-2 pl-6 font-mono"
                      key={model}
                      onSelect={() => pickModel(model)}
                      value={model}
                    >
                      <span className="min-w-0 flex-1 truncate">{model}</span>
                      {warning ? (
                        <span className="shrink-0 text-[0.62rem] lowercase tracking-wide text-warning" title={warning}>
                          no tools
                        </span>
                      ) : null}
                      <span className="shrink-0 text-[0.62rem] lowercase tracking-wide text-muted-foreground/70">
                        {managedModelTag(model, price)}
                      </span>
                      {price && (price.input || price.output) && (
                        <span className="shrink-0 text-[0.66rem] tabular-nums text-muted-foreground" title="Input / Output $/Mtok">
                          {price.input || '?'} / {price.output || '?'}
                        </span>
                      )}
                    </CommandItem>
                  )
                })}
              </CommandGroup>
            </CommandList>
          </Command>
        )}

        <DialogFooter className="flex-row items-center justify-between gap-3 border-t border-border bg-card p-3 sm:justify-between">
          <span className="text-xs text-muted-foreground">
            Planners plan · your current main model works · reviewers critique · main model fuses one answer.
          </span>
          <div className="flex items-center gap-2">
            {phase !== 'plannerCount' && phase !== 'submitting' && (
              <Button onClick={back} variant="ghost">
                Back
              </Button>
            )}
            <Button onClick={() => onOpenChange(false)} variant="outline">
              Cancel
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
