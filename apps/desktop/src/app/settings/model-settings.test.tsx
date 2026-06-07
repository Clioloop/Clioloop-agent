import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const getGlobalModelInfo = vi.fn()
const getGlobalModelOptions = vi.fn()
const getAuxiliaryModels = vi.fn()
const setModelAssignment = vi.fn()

vi.mock('@/clio', () => ({
  getGlobalModelInfo: () => getGlobalModelInfo(),
  getGlobalModelOptions: () => getGlobalModelOptions(),
  getAuxiliaryModels: () => getAuxiliaryModels(),
  setModelAssignment: (body: unknown) => setModelAssignment(body)
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
  setModelAssignment.mockResolvedValue({ provider: 'openrouter', model: 'openai/gpt-oss-20b:free', gateway_tools: [] })
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
