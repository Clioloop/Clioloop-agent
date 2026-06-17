// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  applyTelegramOnboarding: vi.fn(),
  cancelTelegramOnboarding: vi.fn(),
  getTelegramOnboardingStatus: vi.fn(),
  restartGateway: vi.fn(),
  startTelegramOnboarding: vi.fn()
}))

vi.mock('@/clio', () => ({
  applyTelegramOnboarding: (id: string, body: unknown) => mocks.applyTelegramOnboarding(id, body),
  cancelTelegramOnboarding: (id: string) => mocks.cancelTelegramOnboarding(id),
  getTelegramOnboardingStatus: (id: string) => mocks.getTelegramOnboardingStatus(id),
  restartGateway: () => mocks.restartGateway(),
  startTelegramOnboarding: (body: unknown) => mocks.startTelegramOnboarding(body)
}))
vi.mock('qrcode', () => ({ default: { toDataURL: vi.fn().mockResolvedValue('data:image/png;base64,QR') } }))

import { TelegramQrSetup } from './telegram-qr-setup'

describe('TelegramQrSetup', () => {
  beforeEach(() => {
    mocks.startTelegramOnboarding.mockResolvedValue({
      deep_link: 'https://t.me/newbot/ClioSetupBot/clio_x_bot',
      expires_at: new Date(Date.now() + 600_000).toISOString(),
      pairing_id: 'p1',
      qr_payload: 'https://t.me/newbot/ClioSetupBot/clio_x_bot',
      suggested_username: 'clio_x_bot'
    })
    mocks.getTelegramOnboardingStatus.mockResolvedValue({
      bot_username: 'clio_x_bot',
      expires_at: '',
      owner_user_id: '4242',
      status: 'ready'
    })
    mocks.applyTelegramOnboarding.mockResolvedValue({ needs_restart: true, ok: true, platform: 'telegram' })
    mocks.restartGateway.mockResolvedValue({ ok: true })
    mocks.cancelTelegramOnboarding.mockResolvedValue({ ok: true })
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('shows the QR start button initially', () => {
    render(<TelegramQrSetup />)
    expect(screen.getByTestId('telegram-qr-setup')).toBeTruthy()
    expect(screen.getByText('Set up with QR')).toBeTruthy()
  })

  it('runs the full flow: start → QR → ready → apply → restart', async () => {
    const onApplied = vi.fn()
    render(<TelegramQrSetup onApplied={onApplied} />)

    fireEvent.click(screen.getByText('Set up with QR'))
    await waitFor(() => expect(mocks.startTelegramOnboarding).toHaveBeenCalledWith({ bot_name: 'Clioloop' }))

    // QR + deep link shown while waiting.
    await waitFor(() => expect(screen.getByAltText('Telegram setup QR code')).toBeTruthy())
    expect(screen.getByText('open in Telegram').getAttribute('href')).toContain('t.me/newbot/ClioSetupBot/clio_x_bot')

    // Poll resolves ready; the detected owner id is prefilled.
    await waitFor(() => expect(screen.getByText(/Bot created/)).toBeTruthy(), { timeout: 3000 })
    expect(screen.getByText('4242')).toBeTruthy()

    // Apply saves the token with the allowed id and restarts the gateway.
    fireEvent.click(screen.getByText('Save & restart gateway'))
    await waitFor(() =>
      expect(mocks.applyTelegramOnboarding).toHaveBeenCalledWith('p1', { allowed_user_ids: ['4242'] }),
    )
    await waitFor(() => expect(mocks.restartGateway).toHaveBeenCalled())
    await waitFor(() => expect(onApplied).toHaveBeenCalled())
  })

  it('validates that allowed user IDs are numeric', async () => {
    render(<TelegramQrSetup />)
    fireEvent.click(screen.getByText('Set up with QR'))
    await waitFor(() => expect(screen.getByText(/Bot created/)).toBeTruthy(), { timeout: 3000 })

    // Remove the prefilled id, then try to add a non-numeric one.
    fireEvent.click(screen.getByLabelText('Remove 4242'))
    fireEvent.change(screen.getByLabelText('Telegram user ID'), { target: { value: 'abc' } })
    fireEvent.click(screen.getByText('Add'))
    expect(screen.getByText('Allowed Telegram user IDs must be numeric.')).toBeTruthy()
  })
})
