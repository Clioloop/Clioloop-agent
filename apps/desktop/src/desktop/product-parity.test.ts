import { describe, expect, it, vi } from 'vitest'

import {
  addArtifactVersion,
  artifactPreviewVersion,
  createCrashHandoff,
  layoutPaneIds,
  lockArtifactPreview,
  normalizeLayoutTree,
  PluginContributionRegistry,
  rankComposerSuggestions,
  reduceQuickEntry,
  reduceVoiceWake,
  updateCrashHandoffItem,
  upsertComposerReference,
  type AdvancedComposerState,
  type ArtifactCardState,
  type QuickEntryState,
  type VoiceWakeState
} from './product-parity'

const quickState: QuickEntryState = {
  connected: true,
  draft: '  ship it  ',
  error: null,
  submitting: false,
  target: { id: 'current', kind: 'current', label: 'Current chat' },
  visible: true
}

const composerState: AdvancedComposerState = {
  chips: [],
  draft: '',
  inbox: [],
  references: [],
  selectedSuggestionId: null,
  suggestions: []
}

describe('desktop product parity contracts', () => {
  it('normalizes layout trees and preserves deterministic pane traversal', () => {
    const tree = normalizeLayoutTree({
      axis: 'horizontal',
      first: { id: 'chat', kind: 'pane', pane: 'chat' },
      id: 'root',
      kind: 'split',
      ratio: 4,
      second: {
        activeId: 'missing',
        children: [
          { id: 'review', kind: 'pane', pane: 'git-review' },
          { id: 'board', kind: 'pane', pane: 'kanban' }
        ],
        id: 'tools',
        kind: 'tabs'
      }
    })
    expect(tree).toMatchObject({ ratio: 0.9, second: { activeId: 'review' } })
    expect(layoutPaneIds(tree)).toEqual(['chat', 'review', 'board'])
  })

  it('sends Quick Entry once through the selected real-chat target', () => {
    const first = reduceQuickEntry(quickState, { type: 'submit' })
    expect(first.send).toEqual({ target: quickState.target, text: 'ship it' })
    expect(first.state).toMatchObject({ draft: '', submitting: true, visible: false })
    expect(reduceQuickEntry(first.state, { type: 'submit' }).send).toBeNull()
  })

  it('deduplicates references and suggestion providers deterministically', () => {
    const first = upsertComposerReference(composerState, { id: 'readme', kind: 'file', label: 'README', value: '/README.md' })
    const second = upsertComposerReference(first, {
      id: 'readme', kind: 'file', label: 'README locked', locked: true, value: '/README.md'
    })
    expect(second.references).toHaveLength(1)
    expect(second.chips).toEqual([{ id: 'reference:readme', label: 'README locked', referenceId: 'readme', tone: 'locked' }])
    expect(rankComposerSuggestions([
      { id: 'b', label: 'B', provider: 'mcp', score: 4, value: 'b' },
      { id: 'a', label: 'A old', provider: 'skill', score: 1, value: 'a' },
      { id: 'a', label: 'A', provider: 'skill', score: 5, value: 'a' }
    ]).map(item => item.id)).toEqual(['a', 'b'])
  })

  it('loads plugin pages/widgets/commands/settings atomically and unloads deterministically', () => {
    const registry = new PluginContributionRegistry()
    const run = vi.fn()
    const dispose = registry.load('delivery', [
      { id: 'today', kind: 'page', route: '/delivery', title: 'Delivery' },
      { area: 'rail', id: 'status', kind: 'widget', title: 'Status' },
      { id: 'ship', kind: 'command', run, title: 'Ship' },
      { defaultValue: false, id: 'confirm', key: 'confirm', kind: 'setting', title: 'Confirm' }
    ])
    expect(registry.list().map(item => item.kind)).toEqual(['command', 'page', 'setting', 'widget'])
    expect(dispose()).toEqual(['command:ship', 'page:today', 'setting:confirm', 'widget:status'])
    expect(registry.list()).toEqual([])
  })

  it('keeps locked artifact previews stable while newer versions arrive', () => {
    const state: ArtifactCardState = {
      artifactId: 'report',
      currentVersionId: 'v1',
      lockedPreviewVersionId: null,
      title: 'Report',
      versions: [{ createdAt: 1, id: 'v1', label: 'v1', mimeType: 'text/markdown', sourceMessageId: null, url: 'v1.md' }]
    }
    const locked = lockArtifactPreview(state, 'v1')
    const updated = addArtifactVersion(locked, {
      createdAt: 2, id: 'v2', label: 'v2', mimeType: 'text/markdown', sourceMessageId: 'm2', url: 'v2.md'
    })
    expect(updated.currentVersionId).toBe('v2')
    expect(artifactPreviewVersion(updated)?.id).toBe('v1')
  })

  it('guards wake mode on permission and gives crash handoffs one continuation attempt', () => {
    const voice: VoiceWakeState = {
      error: null,
      inputLevel: 0,
      microphonePermission: 'denied',
      mode: 'disabled',
      transcript: '',
      wakeEnabled: false,
      wakePhrase: 'Hey Clio'
    }
    expect(reduceVoiceWake(voice, { type: 'arm' })).toMatchObject({ mode: 'disabled', wakeEnabled: false })

    const handoff = createCrashHandoff({ at: 7, clean: false, reason: 'renderer gone' }, [
      { id: 's1', title: 'Build' }, { id: 's1', title: 'Duplicate' }, { id: 's2', title: 'Test' }
    ])
    expect(handoff?.items).toHaveLength(2)
    const continued = updateCrashHandoffItem(handoff!, 's1', 'continued')
    const duplicateSignal = updateCrashHandoffItem(continued, 's1', 'failed', 'late failure')
    expect(duplicateSignal.items[0]).toMatchObject({ attempt: 1, error: null, status: 'continued' })
    expect(updateCrashHandoffItem(duplicateSignal, 's2', 'skipped').status).toBe('complete')
  })
})
