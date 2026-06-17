# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Clioloop ("Omni Loop") is a self-improving AI agent. The repo is a monorepo with a **Python core**
(the `clio` CLI + agent loop) and several **TypeScript/JS surfaces** (Electron desktop, React-Ink TUI,
React web dashboard), plus the self-hostable **Omni Loop Portal** (Next.js) that provides one-login
access to 300+ models.

## Two install trees (read this first)

This dev repo is **not** what end users run. The live `clio` is a separate installed copy at
`~/.clio/clio-agent` (from the `curl … | bash` installer); `clio update` syncs it. Edits here reach
users only via release. To test changes against the *live* agent, sync them into `~/.clio/clio-agent`
and restart — running from this repo (`uv run clio`) exercises the dev tree only.

`~/.clio/` is the agent home: `config.yaml` (committed defaults) + `config.local.yaml` (git-ignored
overrides), `profiles/`, `cache/`, credentials. `CLIO_HOME` selects the home and is set **before**
module imports, so subprocesses must propagate it explicitly.

## Commands

### Python core (uv)
- Setup: `uv sync --all-extras --dev`
- Run the CLI from source: `uv run clio …` (the root `./clio` wrapper just calls `clio_cli.main:main`)
- **Tests — use the canonical runner, not bare pytest** (it matches CI: per-file process isolation,
  hermetic `env -i`, `TZ=UTC`, cleared credentials, `CLIO_HOME` tempdir; needs a `.venv` from `uv sync`):
  - Full suite: `scripts/run_tests.sh`
  - Single file: `scripts/run_tests.sh tests/agent/test_foo.py`
  - Subtree(s): `scripts/run_tests.sh tests/agent/ tests/acp/`
  - Pass pytest args after `--`: `scripts/run_tests.sh tests/foo.py -- -v --tb=long`
  - Cap parallelism: `scripts/run_tests.sh -j 4`
  - Integration tests are **skipped by default** (`addopts = -m 'not integration'`); opt in with
    `… -- -m integration`.
- **Lint (this is all CI runs):** `source .venv/bin/activate && ruff check .`
  ⚠️ Ruff is deliberately near-disabled: the only enabled rule is `PLW1514` (require an explicit
  `encoding=` on `open()`/`read_text()`/`write_text()` — bare text mode corrupts non-ASCII on Windows).
  Do **not** rely on ruff for style/bug coverage; it intentionally checks almost nothing else.
- Type check (configured via `[tool.ty]`, not in CI): `uv run ty check`

### Node surfaces (npm workspaces, from repo root)
Workspaces are `apps/*`, `packages/*`, `ui-tui`, `ui-tui/packages/*`, `web`. `npm install` at the root
covers them all.
- Desktop (Electron + Vite + React): `npm -w apps/desktop run dev | build | lint | type-check | test:ui`
- TUI (React Ink): `npm -w ui-tui run dev | build | lint | test`
- Web dashboard (React): `npm -w web run dev | build`
- Single vitest test: `cd ui-tui && npx vitest run src/path/foo.test.ts` (or `-t "test name"`)

### Omni Loop Portal (standalone — NOT a workspace)
`portal/` is its own npm project (`omni-loop-portal`); `npm -w portal …` will **not** work — you must `cd`:
```bash
cd portal && npm run setup   # one-time: writes .env.local, installs deps
npm run dev                  # Next.js dev on :4280
npm run build | start | lint
npm test                     # vitest
```
Mock-friendly for local e2e: with no `OPENROUTER_API_KEY` the portal serves everything except real
inference; with no `STRIPE_SECRET_KEY` billing runs in mock mode (plan changes apply instantly).

### Docker
`CLIO_UID=$(id -u) CLIO_GID=$(id -g) docker compose up` — runs the `gateway` + `dashboard` services.

## Architecture (the parts that span multiple files)

### Agent / CLI
Console entry points (`pyproject.toml [project.scripts]`): `clio = clio_cli.main:main`,
`clio-agent = run_agent:main`, `clio-acp = acp_adapter.entry:main`. The CLI in `clio_cli/` dispatches
subcommands; the agent loop (`run_agent.py` + `agent/`) does the tool-calling. Heavy config logic lives
in `clio_cli/config.py` — load via its helpers, don't hand-parse YAML.

**Slash commands** have a single source of truth: `clio_cli/commands.py` (`COMMAND_REGISTRY`, a list of
`CommandDef`). To add one: add a `CommandDef`, then implement the handler in the CLI dispatch and in the
gateway dispatch (`gateway/run.py`); messaging-platform adapters auto-derive help/registration from the
registry. `/fusion` (Pro-plan planner/reviewer/judge model fusion) is **server-side**: the engine
(prompts + pipeline) runs on the portal and lives in the **private** repo `Clioloop/Clioloop-fusion`
(overlaid onto the VPS at deploy time, `.gitignore`'d in this repo under `portal/src/lib/fusion/` and
`portal/src/app/api/v1/fusion/`). `agent/fusion_engine.py` is only a **thin client**: it keeps the
config/parsing/gate/UI helpers and drives the portal's `POST /api/v1/fusion/{start,step}` protocol,
running the full-tool work/revise/finalize turns on the local agent. The public repo contains no
Fusion prompts or pipeline logic.

### Providers
Every inference backend is a `ProviderProfile` (`providers/base.py`); discovery is lazy via
`providers/__init__.py`. Bundled providers live in `plugins/model-providers/<name>/__init__.py` and call
`register_provider()`; user plugins under `$CLIO_HOME/plugins/model-providers/` override on name
collision. The `managed` provider **is** the Omni Loop Portal (OAuth device-code, no API key). Model
catalog + switching: `clio_cli/model_catalog.py` (remote JSON cached under `~/.clio/cache/`) and
`clio_cli/model_switch.py` (the alias→provider→normalize→lookup pipeline).

### Gateway
`gateway/run.py` is a large async event loop for **messaging platforms** (Telegram/Slack/Discord/…),
a separate service from the interactive CLI; adapters live in `gateway/platforms/`. Telegram managed-bot
onboarding: `clio_cli/telegram_managed_bot.py` + portal pairings.

### Omni Loop Portal (`portal/`)
Next.js 15 + SQLite (`better-sqlite3`) + Stripe. Responsibilities: OAuth 2.0 device-code onboarding,
JWT access tokens, an OpenAI-compatible inference proxy, a tool-gateway passthrough, and Stripe billing
with per-user usage metering ("credit micros", 1e6 = €1; plans `free|pro|max|max20x`). Key files:
- `src/lib/db.ts` — SQLite schema (users, subscriptions, oauth/device tokens, usage_events, …)
- `src/lib/tokens.ts` — HS256 access JWTs (`olp_at_*`) + opaque refresh tokens (`olp_rt_*`) with
  single-use rotation and family-based reuse detection
- `src/lib/plans.ts` / `src/lib/billing.ts` — tiers, entitlements, Stripe
- `src/lib/gateway.ts` + `src/app/api/gateway/[vendor]/…` — vendor passthrough (firecrawl, vidu,
  TTS, browser-use, image), swaps the user token for the house upstream key and meters
- `src/app/api/v1/chat/completions/route.ts` — inference proxy (routes to Ollama or OpenRouter)

### Portal ↔ agent contract
Device flow: `POST /api/oauth/device/code` → user approves at `/activate` → `POST /api/oauth/token`
returns `{ access_token (JWT), refresh_token, inference_base_url }`. The agent then sends the Bearer
token to `/api/v1/*` (inference) and `/api/gateway/*` (tools); `GET /api/account/info` returns plan +
entitlements. Agent-side: `clio_cli/auth.py`, `omni_portal.py`, `portal_account.py`,
`portal_subscription.py`, and `tools/managed_tool_gateway.py`. Default base URL is
`https://portal.clioloop.com`; override with `CLIO_PORTAL_BASE_URL`.

## Conventions & gotchas

- **Exact-pin dependency policy.** Every direct Python dep is pinned `==X.Y.Z` (no ranges) as a
  supply-chain measure. When adding/bumping: edit `pyproject.toml` **and** regenerate `uv.lock`
  (`uv lock`). Provider/backend-specific deps belong in an `[project.optional-dependencies]` extra and
  are lazy-installed at first use via `tools/lazy_deps.py` — keep them out of core `dependencies`, and
  note `[all]` deliberately excludes anything lazy-installable.
- **Python 3.11–3.13 only.** The `<3.14` cap in `requires-python` is load-bearing (Rust transitives
  lack cp314 wheels); don't raise it casually.
- **User-facing provider labels** must use `provider_label`/`get_label` (e.g. `managed` → "Omni Loop
  Portal"), never the raw provider key.
- **Tests are hermetic.** No ambient env or real credentials are visible inside tests; rely on fixtures.
