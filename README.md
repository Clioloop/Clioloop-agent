<p align="center">
  <img src="assets/banner.png" alt="Clio Agent" width="100%">
</p>

# Clio Agent ☤

<p align="center">
  <a href="https://clio-agent./docs/"><img src="https://img.shields.io/badge/Docs-clio--agent.-FFD700?style=for-the-badge" alt="Documentation"></a>
  <a href="https://discord.gg/Clioloop"><img src="https://img.shields.io/badge/Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Discord"></a>
  <a href="https://github.com/Clioloop/Clioloop-agent/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License: MIT"></a>
  <a href="https://"><img src="https://img.shields.io/badge/Built%20by-Omni%20Loop%20Labs-blueviolet?style=for-the-badge" alt="Built by Omni Loop Labs"></a>
  <a href="README.zh-CN.md"><img src="https://img.shields.io/badge/Lang-中文-red?style=for-the-badge" alt="中文"></a>
</p>

**The self-improving AI agent built by [Omni Loop Labs](https://).** It's the only agent with a built-in learning loop — it creates skills from experience, improves them during use, nudges itself to persist knowledge, searches its own past conversations, and builds a deepening model of who you are across sessions. Run it on a $5 VPS, a GPU cluster, or serverless infrastructure that costs nearly nothing when idle. It's not tied to your laptop — talk to it from Telegram while it works on a cloud VM.

Use any model you want — [OpenRouter](https://openrouter.ai) (200+ models), [NovitaAI](https://novita.ai) (AI-native cloud for Model API, Agent Sandbox, and GPU Cloud), [NVIDIA NIM](https://build.nvidia.com) (Nemotron), [Xiaomi MiMo](https://platform.xiaomimimo.com), [z.ai/GLM](https://z.ai), [Kimi/Moonshot](https://platform.moonshot.ai), [MiniMax](https://www.minimax.io), [Hugging Face](https://huggingface.co), OpenAI, xAI Grok, or your own endpoint. Switch with `clio model` — no code changes, no lock-in.

<table>
<tr><td><b>A real terminal interface</b></td><td>Full TUI with multiline editing, slash-command autocomplete, conversation history, interrupt-and-redirect, and streaming tool output.</td></tr>
<tr><td><b>Lives where you do</b></td><td>Telegram, Discord, Slack, WhatsApp, Signal, and CLI — all from a single gateway process. Voice memo transcription, cross-platform conversation continuity.</td></tr>
<tr><td><b>A closed learning loop</b></td><td>Agent-curated memory with periodic nudges. Autonomous skill creation after complex tasks. Skills self-improve during use. FTS5 session search with LLM summarization for cross-session recall. <a href="https://github.com/plastic-labs/honcho">Honcho</a> dialectic user modeling. Compatible with the <a href="https://agentskills.io">agentskills.io</a> open standard.</td></tr>
<tr><td><b>Scheduled automations</b></td><td>Built-in cron scheduler with delivery to any platform. Daily reports, nightly backups, weekly audits — all in natural language, running unattended.</td></tr>
<tr><td><b>Delegates and parallelizes</b></td><td>Spawn isolated subagents for parallel workstreams. Write Python scripts that call tools via RPC, collapsing multi-step pipelines into zero-context-cost turns.</td></tr>
<tr><td><b>Runs anywhere, not just your laptop</b></td><td>Six terminal backends — local, Docker, SSH, Singularity, Modal, and Daytona. Daytona and Modal offer serverless persistence — your agent's environment hibernates when idle and wakes on demand, costing nearly nothing between sessions. Run it on a $5 VPS or a GPU cluster.</td></tr>
<tr><td><b>Research-ready</b></td><td>Batch trajectory generation, trajectory compression for training the next generation of tool-calling models.</td></tr>
</table>

---

## Quick Install

### Linux, macOS, WSL2, Termux

```bash
curl -fsSL https://raw.githubusercontent.com/Clioloop/Clioloop-agent/main/scripts/install.sh | bash
```

### Windows (native, PowerShell)

> **Heads up:** Native Windows runs Clio without WSL — CLI, gateway, TUI, and tools all work natively. If you'd rather use WSL2, the Linux/macOS one-liner above works there too. Found a bug? Please [file issues](https://github.com/Clioloop/Clioloop-agent/issues).

Run this in PowerShell:

```powershell
iex (irm https://raw.githubusercontent.com/Clioloop/Clioloop-agent/main/scripts/install.ps1)
```

The installer handles everything: uv, Python 3.11, Node.js, ripgrep, ffmpeg, **and a portable Git Bash** (MinGit, unpacked to `%LOCALAPPDATA%\clio\git` — no admin required, completely isolated from any system Git install). Clio uses this bundled Git Bash to run shell commands.

If you already have Git installed, the installer detects it and uses that instead. Otherwise a ~45MB MinGit download is all you need — it won't touch or interfere with any system Git.

> **Android / Termux:** The tested manual path is documented in the [Termux guide](https://clio-agent./docs/getting-started/termux). On Termux, Clio installs a curated `.[termux]` extra because the full `.[all]` extra currently pulls Android-incompatible voice dependencies.
>
> **Windows:** Native Windows is fully supported — the PowerShell one-liner above installs everything. If you'd rather use WSL2, the Linux command works there too. Native Windows install lives under `%LOCALAPPDATA%\clio`; WSL2 installs under `~/.clio` as on Linux. The only Clio feature that currently needs WSL2 specifically is the browser-based dashboard chat pane (it uses a POSIX PTY — classic CLI and gateway both run natively).

After installation:

```bash
source ~/.bashrc    # reload shell (or: source ~/.zshrc)
clio              # start chatting!
```

---

## Getting Started

```bash
clio              # Interactive CLI — start a conversation
clio model        # Choose your LLM provider and model
clio tools        # Configure which tools are enabled
clio config set   # Set individual config values
clio gateway      # Start the messaging gateway (Telegram, Discord, etc.)
clio setup        # Run the full setup wizard (configures everything at once)
clio claw migrate # Migrate from OpenClaw (if coming from OpenClaw)
clio update       # Update to the latest version
clio doctor       # Diagnose any issues
```

📖 **[Full documentation →](https://clio-agent./docs/)**

---

## Choose your own provider

Clio works with whatever provider you want — that's not changing. Bring your own API key for the model, web search, image generation, TTS, and a cloud browser, or pick a single provider (OpenRouter, xAI, Anthropic, etc.) and run everything through that.

- **300+ models via OpenRouter** — pick any of them with `clio model <name>`
- **First-class providers** — OpenAI, Anthropic, xAI, Google Gemini, DeepSeek, Qwen, Kimi, NVIDIA NIM, Hugging Face, OpenCode, Arcee, GMI, Kilo, AWS Bedrock, Azure Foundry, and many more.

One command from a fresh install:

```bash
clio setup
```

That walks you through the model provider, picks reasonable defaults, and shows you which optional tools you can enable with your own API keys. Full details on the [Setup docs page](https://clio-agent./docs/getting-started/setup).

You can still bring your own keys per-tool whenever you want — configuration is per-tool, not all-or-nothing.

---

## CLI vs Messaging Quick Reference

Clio has two entry points: start the terminal UI with `clio`, or run the gateway and talk to it from Telegram, Discord, Slack, WhatsApp, Signal, or Email. Once you're in a conversation, many slash commands are shared across both interfaces.

| Action                         | CLI                                           | Messaging platforms                                                              |
| ------------------------------ | --------------------------------------------- | -------------------------------------------------------------------------------- |
| Start chatting                 | `clio`                                      | Run `clio gateway setup` + `clio gateway start`, then send the bot a message |
| Start fresh conversation       | `/new` or `/reset`                            | `/new` or `/reset`                                                               |
| Change model                   | `/model [provider:model]`                     | `/model [provider:model]`                                                        |
| Set a personality              | `/personality [name]`                         | `/personality [name]`                                                            |
| Retry or undo the last turn    | `/retry`, `/undo`                             | `/retry`, `/undo`                                                                |
| Compress context / check usage | `/compress`, `/usage`, `/insights [--days N]` | `/compress`, `/usage`, `/insights [days]`                                        |
| Browse skills                  | `/skills` or `/<skill-name>`                  | `/<skill-name>`                                                                  |
| Interrupt current work         | `Ctrl+C` or send a new message                | `/stop` or send a new message                                                    |
| Platform-specific status       | `/platforms`                                  | `/status`, `/sethome`                                                            |

For the full command lists, see the [CLI guide](https://clio-agent./docs/user-guide/cli) and the [Messaging Gateway guide](https://clio-agent./docs/user-guide/messaging).

---

## Documentation

All documentation lives at **[clio-agent./docs](https://clio-agent./docs/)**:

| Section                                                                                             | What's Covered                                             |
| --------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| [Quickstart](https://clio-agent./docs/getting-started/quickstart)                 | Install → setup → first conversation in 2 minutes          |
| [CLI Usage](https://clio-agent./docs/user-guide/cli)                              | Commands, keybindings, personalities, sessions             |
| [Configuration](https://clio-agent./docs/user-guide/configuration)                | Config file, providers, models, all options                |
| [Messaging Gateway](https://clio-agent./docs/user-guide/messaging)                | Telegram, Discord, Slack, WhatsApp, Signal, Home Assistant |
| [Security](https://clio-agent./docs/user-guide/security)                          | Command approval, DM pairing, container isolation          |
| [Tools & Toolsets](https://clio-agent./docs/user-guide/features/tools)            | 40+ tools, toolset system, terminal backends               |
| [Skills System](https://clio-agent./docs/user-guide/features/skills)              | Procedural memory, Skills Hub, creating skills             |
| [Memory](https://clio-agent./docs/user-guide/features/memory)                     | Persistent memory, user profiles, best practices           |
| [MCP Integration](https://clio-agent./docs/user-guide/features/mcp)               | Connect any MCP server for extended capabilities           |
| [Cron Scheduling](https://clio-agent./docs/user-guide/features/cron)              | Scheduled tasks with platform delivery                     |
| [Context Files](https://clio-agent./docs/user-guide/features/context-files)       | Project context that shapes every conversation             |
| [Architecture](https://clio-agent./docs/developer-guide/architecture)             | Project structure, agent loop, key classes                 |
| [Contributing](https://clio-agent./docs/developer-guide/contributing)             | Development setup, PR process, code style                  |
| [CLI Reference](https://clio-agent./docs/reference/cli-commands)                  | All commands and flags                                     |
| [Environment Variables](https://clio-agent./docs/reference/environment-variables) | Complete env var reference                                 |

---

## Migrating from OpenClaw

If you're coming from OpenClaw, Clio can automatically import your settings, memories, skills, and API keys.

**During first-time setup:** The setup wizard (`clio setup`) automatically detects `~/.openclaw` and offers to migrate before configuration begins.

**Anytime after install:**

```bash
clio claw migrate              # Interactive migration (full preset)
clio claw migrate --dry-run    # Preview what would be migrated
clio claw migrate --preset user-data   # Migrate without secrets
clio claw migrate --overwrite  # Overwrite existing conflicts
```

What gets imported:

- **SOUL.md** — persona file
- **Memories** — MEMORY.md and USER.md entries
- **Skills** — user-created skills → `~/.clio/skills/openclaw-imports/`
- **Command allowlist** — approval patterns
- **Messaging settings** — platform configs, allowed users, working directory
- **API keys** — allowlisted secrets (Telegram, OpenRouter, OpenAI, Anthropic, ElevenLabs)
- **TTS assets** — workspace audio files
- **Workspace instructions** — AGENTS.md (with `--workspace-target`)

See `clio claw migrate --help` for all options, or use the `openclaw-migration` skill for an interactive agent-guided migration with dry-run previews.

---

## Contributing

We welcome contributions! See the [Contributing Guide](https://clio-agent./docs/developer-guide/contributing) for development setup, code style, and PR process.

Quick start for contributors — clone and go with `setup-clio.sh`:

```bash
git clone https://github.com/Clioloop/Clioloop-agent.git
cd clio-agent
./setup-clio.sh     # installs uv, creates venv, installs .[all], symlinks ~/.local/bin/clio
./clio              # auto-detects the venv, no need to `source` first
```

Manual path (equivalent to the above):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv .venv --python 3.11
source .venv/bin/activate
uv pip install -e ".[all,dev]"
scripts/run_tests.sh
```

---

## Community

- 💬 [Discord](https://discord.gg/Clioloop)
- 📚 [Skills Hub](https://agentskills.io)
- 🐛 [Issues](https://github.com/Clioloop/Clioloop-agent/issues)
- 🔌 [computer-use-linux](https://github.com/avifenesh/computer-use-linux) — Linux desktop-control MCP server for Clio and other MCP hosts, with AT-SPI accessibility trees, Wayland/X11 input, screenshots, and compositor window targeting.
- 🔌 [ClioClaw](https://github.com/AaronWong1999/clioclaw) — Community WeChat bridge: Run Clio Agent and OpenClaw on the same WeChat account.

---

## License

MIT — see [LICENSE](LICENSE).

Built by [Omni Loop Labs](https://).
