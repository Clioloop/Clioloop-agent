# ∞ Omni Loop Portal

The official account, billing, and managed model-access portal for
[Clioloop](https://github.com/Clioloop/Clioloop-agent). One login gives every
Clioloop surface (CLI, TUI, desktop app, web dashboard) access to 300+ models
through a single OpenAI-compatible endpoint, routed via OpenRouter.

## What's inside

| Area | Details |
|---|---|
| Marketing site | Landing page, pricing, docs & tutorials |
| Accounts | Email/password auth, session cookies (JWT) |
| Billing | Stripe subscriptions: Free (card verification), Pro €20, Max €100, Max 20x €250 — automatic **mock mode** without a Stripe key |
| Device OAuth | RFC 8628 device-code flow consumed by `clio setup` / `clio auth add managed` — rotating single-use refresh tokens with reuse detection |
| Inference proxy | `POST /api/v1/chat/completions` + `GET /api/v1/models`, streaming SSE pass-through, per-request cost metering, per-plan monthly allowances, free-tier model gating |
| API keys | Long-lived `olp_sk_…` keys for scripts/CI, managed from the dashboard |

## One-click setup

```bash
cd portal
npm run setup     # creates .env.local, installs deps
npm run dev       # → http://localhost:4280
```

Then point a local Clioloop at it:

```bash
export CLIO_PORTAL_BASE_URL=http://localhost:4280
clio setup        # pick "Omni Loop Portal"
```

Without `OPENROUTER_API_KEY` the portal serves everything except actual
inference; without `STRIPE_SECRET_KEY` billing runs in mock mode (plan changes
apply instantly). That makes the full flow testable end-to-end with zero
external accounts.

## Production checklist

1. **Deploy** (Vercel, or `npm run build && npm start` behind a reverse proxy).
   Set `PORTAL_BASE_URL` to the public URL. SQLite lives in `PORTAL_DATA_DIR` —
   use a persistent volume (or swap `src/lib/db.ts` for Postgres at scale).
2. **OpenRouter**: create a key at openrouter.ai/keys, load it with credit, set
   `OPENROUTER_API_KEY`. The proxy meters each request's real cost against the
   user's plan allowance (see `src/lib/plans.ts` to tune margins).
3. **Stripe**: create three recurring EUR prices (€20 / €100 / €250 monthly),
   set `STRIPE_PRICE_PRO|MAX|MAX20X`, `STRIPE_SECRET_KEY`, and point a webhook
   at `/api/billing/webhook` (events: `checkout.session.completed`,
   `customer.subscription.*`) with `STRIPE_WEBHOOK_SECRET`.
4. **Clioloop release**: set the portal URL as `DEFAULT_MANAGED_PORTAL_URL` in
   `clio_cli/auth.py` (users can always override with `CLIO_PORTAL_BASE_URL`).

## API surface (consumed by the Clioloop CLI)

```
POST /api/oauth/device/code      device authorization (form: client_id, scope)
POST /api/oauth/token            device_code + refresh_token grants
GET  /api/account/info           plan/entitlement info (Bearer)
GET  /api/v1/models              OpenAI-style model list (Bearer)
POST /api/v1/chat/completions    OpenAI-compatible inference proxy (Bearer)
```

## Plans

Defined in `src/lib/plans.ts`. Usage is metered in "credit micros"
(1,000,000 = €1 of upstream spend) and enforced per calendar month.

| Plan | Price | Models | Allowance |
|---|---|---|---|
| Free | €0 + card verification | `:free` models | €1/mo |
| Pro | €20/mo | all models | €17/mo |
| Max | €100/mo | all models | €85/mo (≈5× Pro) |
| Max 20x | €250/mo | all models | €340/mo (≈20× Pro) |
