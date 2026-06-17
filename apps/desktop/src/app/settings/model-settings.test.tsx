import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const getGlobalModelInfo = vi.fn()
const getGlobalModelOptions = vi.fn()
const getAuxiliaryModels = vi.fn()
const getPortalConnectStatus = vi.fn()
const getPortalStatus = vi.fn()
const setModelAssignment = vi.fn()
const startPortalConnect = vi.fn()

vi.mock('@/clio', () => ({
  getGlobalModelInfo: () => getGlobalModelInfo(),
  getGlobalModelOptions: () => getGlobalModelOptions(),
  getAuxiliaryModels: () => getAuxiliaryModels(),
  getPortalConnectStatus: () => getPortalConnectStatus(),
  getPortalStatus: () => getPortalStatus(),
  setModelAssignment: (body: unknown) => setModelAssignment(body),
  startPortalConnect: () => startPortalConnect()
}))

beforeEach(() => {
  getGlobalModelInfo.mockResolvedValue({ provider: 'openrouter', model: 'openai/gpt-oss-20b:free' })
  getGlobalModelOptions.mockResolvedValue({
    providers: [{ name: 'OpenRouter', slug: 'openrouter', models: ['openai/gpt-oss-20b:free'] }]
  })
  getAuxiliaryModels.mockResolvedValue({
    main: { provider: 'openrouter', model: 'openai/gpt-oss-20b:free' },
    tasks: [{ task: 'vision', provider: 'auto', model: '', base_url: '' }]
  })
  getPortalConnectStatus.mockResolvedValue({ status: 'idle' })
  getPortalStatus.mockResolvedValue({
    inference_url: null,
    logged_in: false,
    portal_url: null,
    provider: 'managed',
    subscription_url: ''
  })
  setModelAssignment.mockResolvedValue({ provider: 'openrouter', model: 'openai/gpt-oss-20b:free', gateway_tools: [] })
  startPortalConnect.mockResolvedValue({
    expires_in: 600,
    status: 'pending',
    user_code: 'ABCD-EFGH',
    verification_uri: 'https://portal.example/activate',
    verification_uri_complete: 'https://portal.example/activate?user_code=ABCD-EFGH'
  })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

async function renderModelSettings() {
  const { ModelSettings } = await import('./model-settings')

  return render(<ModelSettings />)
}

describe('ModelSettings', () => {
  it('loads and shows the current main model', async () => {
    await renderModelSettings()

    await waitFor(() => expect(getGlobalModelInfo).toHaveBeenCalled())
    expect(screen.getByText('OpenRouter')).toBeTruthy()
    expect(screen.getByText('openai/gpt-oss-20b:free')).toBeTruthy()
  })

  it('renders the auxiliary task rows', async () => {
    await renderModelSettings()

    expect(await screen.findByText('Vision')).toBeTruthy()
    expect(screen.getAllByText('auto · use main model').length).toBeGreaterThan(0)
  })

  it('assigns an auxiliary task to the main model via setModelAssignment', async () => {
    await renderModelSettings()

    // One "Set to main" button per task slot; the first is Vision.
    const setToMainButtons = await screen.findAllByRole('button', { name: 'Set to main' })
    fireEvent.click(setToMainButtons[0])

    await waitFor(() =>
      expect(setModelAssignment).toHaveBeenCalledWith({
        model: 'openai/gpt-oss-20b:free',
        provider: 'openrouter',
        scope: 'auxiliary',
        task: 'vision'
      })
    )
  })
})
