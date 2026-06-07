---
title: "managed provider Tool Gateway"
description: "One subscription, every tool. Web search, image generation, TTS, and cloud browsers — all routed through managed provider with no extra API keys."
sidebar_label: "Tool Gateway"
sidebar_position: 2
---

# managed provider Tool Gateway

**One subscription. Every tool built in.**

The Tool Gateway is included with every paid [managed provider](https://) subscription. It routes Clio' tool calls — web search, image generation, text-to-speech, and cloud browser automation — through infrastructure managed provider already runs, so you don't have to sign up with Firecrawl, FAL, OpenAI, Browser Use, or anyone else just to make your agent useful.

<div style={{display: 'flex', gap: '1rem', flexWrap: 'wrap', margin: '1.5rem 0'}}>
  <a href="https:///manage-subscription" style={{background: 'var(--ifm-color-primary)', color: 'white', padding: '0.75rem 1.5rem', borderRadius: '6px', textDecoration: 'none', fontWeight: 'bold'}}>Start or manage subscription →</a>
</div>

## What's included

| | Tool | What you get |
|---|---|---|
| 🔍 | **Web search & extract** | Agent-grade web search and full-page extraction via Firecrawl. No rate limits to worry about — the gateway handles scaling. |
| 🎨 | **Image generation** | Nine models under one endpoint: **FLUX 2 Klein 9B**, **FLUX 2 Pro**, **Z-Image Turbo**, **Nano Banana Pro** (Gemini 3 Pro Image), **GPT Image 1.5**, **GPT Image 2**, **Ideogram V3**, **Recraft V4 Pro**, **Qwen Image**. Pick per-generation with a flag, or let Clio default to FLUX 2 Klein. |
| 🔊 | **Text-to-speech** | OpenAI TTS voices wired into the `text_to_speech` tool. Drop voice notes into Telegram, generate audio for pipelines, narrate anything. |
| 🌐 | **Cloud browser automation** | Headless Chromium sessions via Browser Use. `browser_navigate`, `browser_click`, `browser_type`, `browser_vision` — all the agent-driving primitives, no Browserbase account required. |

All four are pay-as-you-use billed against your managed-provider subscription. Use any combination — run the gateway for web and images while keeping your own ElevenLabs key for TTS, or route everything through managed provider.

## Why it's here

Building an agent that can actually *do things* means stitching together 5+ API subscriptions — each with their own signup, rate limits, billing, and quirks. The gateway collapses that into one account:

- **One bill.** Pay managed provider; we handle the rest.
- **One signup.** No Firecrawl, FAL, Browser Use, or OpenAI audio accounts to manage.
- **One key.** Your managed provider OAuth covers every tool.
- **Same quality.** Same backends the direct-key route uses — just fronted by us.

Bring your own keys anytime — per-tool, whenever you want to. The gateway isn't a lock-in, it's a shortcut.

## Get started

There are three ways in — pick whichever fits where you are:

```bash
clio setup --portal     # Fresh install: managed-provider OAuth + set managed provider as provider + turn on the Tool Gateway in one go
```

```bash
clio model              # Switch your inference provider to managed provider — Clio then offers to turn on the gateway for all tools
```

```bash
clio tools              # Enable the gateway per-tool — pick "managed-provider subscription" for any tool you want
```

`clio setup --portal` and `clio model` are the all-at-once paths: log in once, optionally flip every tool to the gateway. `clio tools` is the à la carte path — turn on just the tools you want, one at a time.

**You don't have to log in first.** With `clio tools`, the managed-provider backends (Web search, Image, Video, TTS, Browser) are always listed, even if you've never signed into managed provider. Select one and Clio runs the Portal login right there if you aren't already authenticated — no need to run `clio model` beforehand. If your managed-provider OAuth is already active, selecting the backend enables it immediately with no extra prompt. This path only logs you in and turns on the one tool you picked — it does **not** switch your inference provider, and it does **not** prompt you to enable the gateway for every other tool.

Check what's active at any time:

```bash
clio portal info        # Portal auth + Tool Gateway routing summary
clio portal tools       # Gateway catalog with current routing per tool
clio status             # Full system status (Tool Gateway is one section)
```

`clio portal info` shows a section like:

```
◆ managed provider Tool Gateway
  managed provider     ✓ managed tools available
  Web tools       ✓ active via managed-provider subscription
  Image gen       ✓ active via managed-provider subscription
  TTS             ✓ active via managed-provider subscription
  Browser         ○ active via Browser Use key
```

Tools marked "active via managed-provider subscription" are going through the gateway. Anything else is using your own keys.

## Eligibility

The Tool Gateway is a **paid-subscription** feature. Free-tier managed-provider accounts can use Portal for inference but don't include managed tools — [upgrade your plan](https:///manage-subscription) to unlock the gateway.

## Mix and match

The gateway is per-tool. Turn it on for just what you want:

- **All tools through managed provider** — easiest; one subscription, done.
- **Gateway for web + images, bring your own TTS** — keep your ElevenLabs voice, let managed provider handle the rest.
- **Gateway only for things you don't have keys for** — "I already pay for Browserbase, but I don't want a Firecrawl account" works fine.

Switch any tool at any time via:

```bash
clio tools          # Interactive picker for each tool category
```

Select the tool, pick **managed-provider subscription** as the provider (or any direct provider you prefer). No config editing required. If you aren't logged into managed provider yet, picking **managed-provider subscription** kicks off the Portal login inline — you don't need to authenticate through `clio model` first.

## Using individual image models

Image generation defaults to FLUX 2 Klein 9B for speed. Override per-call by passing the model ID to the `image_generate` tool:

| Model | ID | Best for |
|---|---|---|
| FLUX 2 Klein 9B | `fal-ai/flux-2/klein/9b` | Fast, good default |
| FLUX 2 Pro | `fal-ai/flux-2/pro` | Higher fidelity FLUX |
| Z-Image Turbo | `fal-ai/z-image/turbo` | Stylized, fast |
| Nano Banana Pro | `fal-ai/gemini-3-pro-image` | Google Gemini 3 Pro Image |
| GPT Image 1.5 | `fal-ai/gpt-image-1/5` | OpenAI image gen, text+image |
| GPT Image 2 | `fal-ai/gpt-image-2` | OpenAI latest |
| Ideogram V3 | `fal-ai/ideogram/v3` | Strong prompt adherence + typography |
| Recraft V4 Pro | `fal-ai/recraft/v4/pro` | Vector-style, graphic design |
| Qwen Image | `fal-ai/qwen-image` | Alibaba multimodal |

The set evolves — `clio tools` → Image Generation shows the current live list.

---

## Configuration reference

Most users never need to touch this — `clio model` and `clio tools` cover every workflow interactively. This section is for writing config.yaml directly or scripting setups.

### Per-tool `use_gateway` flag

Each tool's config block takes a `use_gateway` boolean:

```yaml
web:
  backend: firecrawl
  use_gateway: true

image_gen:
  use_gateway: true

tts:
  provider: openai
  use_gateway: true

browser:
  cloud_provider: browser-use
  use_gateway: true
```

Precedence: `use_gateway: true` routes through managed provider regardless of any direct keys in `.env`. `use_gateway: false` (or absent) uses direct keys if available and only falls back to the gateway when none exist.

### Disabling the gateway

```yaml
web:
  use_gateway: false   # Clio now uses FIRECRAWL_API_KEY from .env
```

`clio tools` automatically clears the flag when you pick a non-gateway provider, so this usually happens for you.

### Self-hosted gateway (advanced)

Running your own managed provider-compatible gateway? Override endpoints in `~/.clio/.env`:

```bash
TOOL_GATEWAY_DOMAIN=your-domain.example.com
TOOL_GATEWAY_SCHEME=https
TOOL_GATEWAY_USER_TOKEN=your-token        # normally auto-populated from Portal login
FIRECRAWL_GATEWAY_URL=https://...         # override one endpoint specifically
```

These knobs exist for custom infrastructure setups (enterprise deployments, dev environments). Regular subscribers never set them.

## FAQ

### Does it work with Telegram / Discord / the other messaging gateways?

Yes. Tool Gateway operates at the tool-execution layer, not the CLI. Every interface that can call a tool — CLI, Telegram, Discord, Slack, IRC, Teams, the API server, anything — benefits from it transparently.

### What happens if my subscription expires?

Tools routed through the gateway stop working until you renew or swap in direct API keys via `clio tools`. Clio shows a clear error pointing at the portal.

### Can I see usage or costs per tool?

Yes — the [managed provider dashboard](https://) breaks usage down by tool so you can see what's driving your bill.

### Is Modal (serverless terminal) included?

Modal is available as an **optional add-on** through the managed-provider subscription, not part of the default Tool Gateway bundle. Configure it via `clio setup terminal` or directly in `config.yaml` when you want a remote sandbox for shell execution.

### Do I need to delete my existing API keys when I enable the gateway?

No — keep them in `.env`. When `use_gateway: true`, Clio skips direct keys and uses the gateway. Flip the flag back to `false` and your keys become the source again. The gateway isn't a lock-in.
