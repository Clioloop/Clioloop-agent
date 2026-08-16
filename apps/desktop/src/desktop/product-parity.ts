/**
 * Renderer-safe state contracts for desktop-only product surfaces.
 *
 * These models deliberately contain no React, Electron, gateway, or storage
 * dependencies. Main/renderer adapters can persist and transport them while
 * tests exercise the user-visible state transitions in one place.
 */

export const DESKTOP_PRODUCT_CONTRACT_VERSION = 1 as const
export const DESKTOP_PRODUCT_FEATURES = Object.freeze([
  'windows',
  'layout-tree',
  'quick-entry',
  'hud',
  'floating-panes',
  'project-review-rail',
  'operations',
  'composer-context',
  'plugins',
  'artifact-history',
  'voice-wake',
  'crash-handoff'
] as const)

export type DesktopWindowKind = 'hud' | 'primary' | 'quick-entry' | 'session' | 'watch'
export type PaneKind = 'artifact' | 'chat' | 'cron' | 'delegations' | 'git-review' | 'kanban' | 'mcp' | `plugin:${string}`

export interface WindowBounds { height: number; width: number; x: number; y: number }
export interface DesktopWindowState {
  alwaysOnTop: boolean
  bounds: WindowBounds
  connectionId: string
  id: string
  kind: DesktopWindowKind
  profile: null | string
  sessionId: null | string
  visible: boolean
}

export interface PaneLeaf {
  id: string
  kind: 'pane'
  pane: PaneKind
  resourceId?: string
}
export interface PaneSplit {
  axis: 'horizontal' | 'vertical'
  first: LayoutNode
  id: string
  kind: 'split'
  ratio: number
  second: LayoutNode
}
export interface PaneTabs {
  activeId: string
  children: PaneLeaf[]
  id: string
  kind: 'tabs'
}
export type LayoutNode = PaneLeaf | PaneSplit | PaneTabs

export interface FloatingPaneState {
  bounds: WindowBounds
  collapsed: boolean
  id: string
  pane: PaneLeaf
  pinned: boolean
  zIndex: number
}

export interface DesktopLayoutState {
  floating: FloatingPaneState[]
  root: LayoutNode
  version: 1
}

export function normalizeLayoutTree(node: LayoutNode): LayoutNode {
  if (node.kind === 'pane') {return { ...node, id: node.id.trim() }}

  if (node.kind === 'tabs') {
    const children = node.children.map(child => normalizeLayoutTree(child) as PaneLeaf)
    const activeId = children.some(child => child.id === node.activeId) ? node.activeId : (children[0]?.id ?? '')

    return { ...node, activeId, children }
  }

  return {
    ...node,
    ratio: Math.min(0.9, Math.max(0.1, Number.isFinite(node.ratio) ? node.ratio : 0.5)),
    first: normalizeLayoutTree(node.first),
    second: normalizeLayoutTree(node.second)
  }
}

export function layoutPaneIds(node: LayoutNode): string[] {
  if (node.kind === 'pane') {return [node.id]}

  if (node.kind === 'tabs') {return node.children.map(child => child.id)}

  return [...layoutPaneIds(node.first), ...layoutPaneIds(node.second)]
}

export interface QuickEntryTarget { id: string; kind: 'current' | 'new' | 'session'; label: string }
export interface QuickEntryState {
  connected: boolean
  draft: string
  error: null | string
  submitting: boolean
  target: QuickEntryTarget
  visible: boolean
}
export type QuickEntryEvent =
  | { draft: string; type: 'edit' }
  | { connected: boolean; type: 'connection' }
  | { target: QuickEntryTarget; type: 'target' }
  | { type: 'dismiss' | 'show' | 'submit' }
export interface QuickEntryTransition { send: null | { target: QuickEntryTarget; text: string }; state: QuickEntryState }

export function reduceQuickEntry(state: QuickEntryState, event: QuickEntryEvent): QuickEntryTransition {
  if (event.type === 'edit') {return { send: null, state: { ...state, draft: event.draft, error: null } }}

  if (event.type === 'connection') {return { send: null, state: { ...state, connected: event.connected } }}

  if (event.type === 'target') {return { send: null, state: { ...state, target: event.target } }}

  if (event.type === 'dismiss') {
    return { send: null, state: { ...state, draft: '', error: null, submitting: false, visible: false } }
  }

  if (event.type === 'show') {return { send: null, state: { ...state, error: null, submitting: false, visible: true } }}
  const text = state.draft.trim()

  if (!text || !state.connected || state.submitting) {return { send: null, state }}

  return {
    send: { target: state.target, text },
    state: { ...state, draft: '', error: null, submitting: true, visible: false }
  }
}

export interface HudState {
  expanded: boolean
  focused: boolean
  opacity: number
  sessionId: null | string
  visible: boolean
}

export type ReviewScope = 'branch' | 'last-turn' | 'uncommitted'
export interface ProjectRailItem {
  activeWorktree: null | string
  branch: null | string
  connectionId: string
  dirtyFiles: number
  id: string
  name: string
  path: string
}
export interface GitReviewRailState {
  baseRef: null | string
  files: Array<{ added: number; path: string; removed: number; staged: boolean; status: string }>
  loading: boolean
  projectId: null | string
  scope: ReviewScope
  selectedPath: null | string
}
export interface ProjectRailState {
  collapsed: boolean
  projects: ProjectRailItem[]
  review: GitReviewRailState
  selectedProjectId: null | string
}

export function selectReviewFile(state: GitReviewRailState, path: null | string): GitReviewRailState {
  return { ...state, selectedPath: path && state.files.some(file => file.path === path) ? path : null }
}

export type LiveStatus = 'blocked' | 'cancelled' | 'failed' | 'queued' | 'running' | 'succeeded'
export interface DelegationViewModel {
  childSessionId: null | string
  completedTasks: number
  id: string
  parentSessionId: string
  status: LiveStatus
  title: string
  totalTasks: number
  updatedAt: number
}
export type KanbanColumn = 'backlog' | 'blocked' | 'doing' | 'done' | 'review'
export interface KanbanCardViewModel {
  assigneeId: null | string
  column: KanbanColumn
  id: string
  order: number
  projectId: string
  title: string
  updatedAt: number
}
export interface CronViewModel {
  enabled: boolean
  id: string
  lastRunAt: null | number
  name: string
  nextRunAt: null | number
  schedule: string
  status: 'disabled' | 'failed' | 'idle' | 'running'
}
export interface McpServerViewModel {
  error: null | string
  id: string
  name: string
  status: 'connecting' | 'disabled' | 'error' | 'ready'
  toolCount: number
  transport: 'http' | 'stdio' | 'sse'
}
export interface OperationsViewModel {
  cron: CronViewModel[]
  delegations: DelegationViewModel[]
  kanban: KanbanCardViewModel[]
  mcp: McpServerViewModel[]
  updatedAt: number
}

export type ComposerReferenceKind = 'artifact' | 'file' | 'mcp-tool' | 'project' | 'session' | 'url'
export interface ComposerReference {
  id: string
  kind: ComposerReferenceKind
  label: string
  locked?: boolean
  metadata?: Readonly<Record<string, string>>
  value: string
}
export interface ComposerChip { id: string; label: string; referenceId: string; tone: 'default' | 'locked' | 'warning' }
export interface ComposerSuggestion {
  detail?: string
  id: string
  label: string
  provider: 'command' | 'cron' | 'file' | 'github' | 'mcp' | 'project' | 'skill'
  score: number
  value: string
}
export interface ComposerInboxItem {
  createdAt: number
  id: string
  kind: 'delegation' | 'mention' | 'result' | 'scheduled'
  read: boolean
  reference?: ComposerReference
  summary: string
}
export interface AdvancedComposerState {
  chips: ComposerChip[]
  draft: string
  inbox: ComposerInboxItem[]
  references: ComposerReference[]
  selectedSuggestionId: null | string
  suggestions: ComposerSuggestion[]
}

export function upsertComposerReference(
  state: AdvancedComposerState,
  reference: ComposerReference
): AdvancedComposerState {
  const references = [...state.references.filter(item => item.id !== reference.id), reference]

  const chip: ComposerChip = {
    id: `reference:${reference.id}`,
    label: reference.label,
    referenceId: reference.id,
    tone: reference.locked ? 'locked' : 'default'
  }

  return { ...state, chips: [...state.chips.filter(item => item.referenceId !== reference.id), chip], references }
}

export function rankComposerSuggestions(suggestions: ComposerSuggestion[], limit = 8): ComposerSuggestion[] {
  const byId = new Map(suggestions.map(item => [item.id, item]))

  return [...byId.values()]
    .sort((a, b) => b.score - a.score || a.provider.localeCompare(b.provider) || a.id.localeCompare(b.id))
    .slice(0, Math.max(0, limit))
}

export type PluginContributionKind = 'command' | 'page' | 'setting' | 'widget'
interface PluginContributionBase { id: string; order?: number; title: string }
export interface PluginPageContribution extends PluginContributionBase { kind: 'page'; route: string }
export interface PluginWidgetContribution extends PluginContributionBase { area: string; kind: 'widget' }
export interface PluginCommandContribution extends PluginContributionBase {
  kind: 'command'
  run: (context?: unknown) => Promise<void> | void
  shortcut?: string
}
export interface PluginSettingContribution extends PluginContributionBase {
  defaultValue: boolean | number | string
  key: string
  kind: 'setting'
}
export type PluginContribution =
  | PluginCommandContribution
  | PluginPageContribution
  | PluginSettingContribution
  | PluginWidgetContribution
export type RegisteredPluginContribution = PluginContribution & { pluginId: string; registeredAt: number }

/** Atomic plugin registry. Failed loads leave the prior registry untouched;
 * unload removes exactly that plugin and reports a stable kind/id order. */
export class PluginContributionRegistry {
  readonly #entries = new Map<string, RegisteredPluginContribution>()
  readonly #plugins = new Map<string, string[]>()
  #revision = 0

  get revision(): number { return this.#revision }

  load(pluginId: string, contributions: readonly PluginContribution[]): () => string[] {
    const normalizedId = pluginId.trim()

    if (!normalizedId) {throw new Error('pluginId is required')}
    const keys = contributions.map(item => `${item.kind}:${item.id.trim()}`)

    if (keys.some(key => key.endsWith(':')) || new Set(keys).size !== keys.length) {
      throw new Error(`Plugin ${normalizedId} has empty or duplicate contribution ids`)
    }

    for (const key of keys) {
      const owner = this.#entries.get(key)?.pluginId

      if (owner && owner !== normalizedId) {throw new Error(`Contribution ${key} is already owned by ${owner}`)}
    }

    this.unload(normalizedId)
    const registeredAt = ++this.#revision
    contributions.forEach((item, index) => {
      const key = keys[index]

      if (key) {this.#entries.set(key, { ...item, id: item.id.trim(), pluginId: normalizedId, registeredAt })}
    })
    this.#plugins.set(normalizedId, keys)

    return () => this.unload(normalizedId)
  }

  list(kind?: PluginContributionKind): readonly RegisteredPluginContribution[] {
    return [...this.#entries.values()]
      .filter(item => !kind || item.kind === kind)
      .sort((a, b) =>
        (a.order ?? 0) - (b.order ?? 0) ||
        a.kind.localeCompare(b.kind) ||
        a.pluginId.localeCompare(b.pluginId) ||
        a.id.localeCompare(b.id))
  }

  unload(pluginId: string): string[] {
    const keys = this.#plugins.get(pluginId) ?? []
    const removed = [...keys].sort()

    for (const key of removed) {this.#entries.delete(key)}

    if (keys.length) {
      this.#plugins.delete(pluginId)
      this.#revision += 1
    }

    return removed
  }
}

export interface ArtifactVersion {
  createdAt: number
  id: string
  label: string
  mimeType: string
  sourceMessageId: null | string
  url: string
}
export interface ArtifactCardState {
  artifactId: string
  currentVersionId: string
  lockedPreviewVersionId: null | string
  title: string
  versions: ArtifactVersion[]
}

export function addArtifactVersion(state: ArtifactCardState, version: ArtifactVersion): ArtifactCardState {
  const versions = [...state.versions.filter(item => item.id !== version.id), version]
    .sort((a, b) => a.createdAt - b.createdAt || a.id.localeCompare(b.id))

  return { ...state, currentVersionId: version.id, versions }
}

export function lockArtifactPreview(state: ArtifactCardState, versionId: null | string): ArtifactCardState {
  if (versionId && !state.versions.some(version => version.id === versionId)) {return state}

  return { ...state, lockedPreviewVersionId: versionId }
}

export function artifactPreviewVersion(state: ArtifactCardState): ArtifactVersion | null {
  const id = state.lockedPreviewVersionId ?? state.currentVersionId

  return state.versions.find(version => version.id === id) ?? null
}

export interface VoiceWakeState {
  error: null | string
  inputLevel: number
  microphonePermission: 'denied' | 'granted' | 'prompt' | 'unavailable'
  mode: 'disabled' | 'listening' | 'processing' | 'speaking' | 'wake-armed'
  transcript: string
  wakeEnabled: boolean
  wakePhrase: string
}
export type VoiceWakeEvent =
  | { error: string; type: 'error' }
  | { level: number; type: 'level' }
  | { transcript: string; type: 'heard' }
  | { type: 'arm' | 'disable' | 'processing' | 'speaking' | 'wake' }

export function reduceVoiceWake(state: VoiceWakeState, event: VoiceWakeEvent): VoiceWakeState {
  if (event.type === 'level') {return { ...state, inputLevel: Math.min(1, Math.max(0, event.level)) }}

  if (event.type === 'heard') {return { ...state, transcript: event.transcript }}

  if (event.type === 'error') {return { ...state, error: event.error, mode: 'disabled' }}

  if (event.type === 'disable') {return { ...state, inputLevel: 0, mode: 'disabled', wakeEnabled: false }}

  if (event.type === 'arm') {return state.microphonePermission === 'granted'
    ? { ...state, error: null, mode: 'wake-armed', wakeEnabled: true }
    : { ...state, error: 'Microphone permission is required', mode: 'disabled' }}

  if (event.type === 'wake') {return { ...state, error: null, mode: 'listening', transcript: '' }}

  return { ...state, mode: event.type }
}

export type HandoffItemStatus = 'continued' | 'failed' | 'pending' | 'skipped'
export interface CrashHandoffItem {
  attempt: number
  error: null | string
  sessionId: string
  status: HandoffItemStatus
  title: string
}
export interface CrashAutoContinueHandoff {
  crashAt: number
  handoffId: string
  items: CrashHandoffItem[]
  reason: null | string
  status: 'complete' | 'offered' | 'running'
  version: 1
}

export function createCrashHandoff(
  crash: { at: number; clean: boolean; reason?: string },
  sessions: Array<{ id: string; title: string }>
): CrashAutoContinueHandoff | null {
  if (crash.clean || sessions.length === 0) {return null}
  const unique = [...new Map(sessions.filter(item => item.id.trim()).map(item => [item.id, item])).values()]

  if (!unique.length) {return null}

  return {
    version: 1,
    crashAt: crash.at,
    handoffId: `crash:${crash.at}`,
    items: unique.map(item => ({ attempt: 0, error: null, sessionId: item.id, status: 'pending', title: item.title })),
    reason: crash.reason?.slice(0, 8_192) || null,
    status: 'offered'
  }
}

export function updateCrashHandoffItem(
  handoff: CrashAutoContinueHandoff,
  sessionId: string,
  status: Exclude<HandoffItemStatus, 'pending'>,
  error: null | string = null
): CrashAutoContinueHandoff {
  const items = handoff.items.map(item => item.sessionId !== sessionId || item.attempt > 0
    ? item
    : { ...item, attempt: 1, error, status })

  const complete = items.every(item => item.status !== 'pending')

  return { ...handoff, items, status: complete ? 'complete' : 'running' }
}
