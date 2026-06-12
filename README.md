<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="web/public/brand/banner.png">
    <img src="web/public/brand/banner.png" width="700" alt="Clioloop">
  </picture>
</p>

<p align="center">
  <em>The agent that evolves with you, works for you and does not stop its autonomous loops untill it achieves its goal.</em>
</p>

<p align="center">
  <a href="#install"><strong>Install</strong></a> ·
  <a href="#features"><strong>Features</strong></a> ·
  <a href="#commands"><strong>Commands</strong></a> ·
  <a href="#development"><strong>Develop</strong></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11%2B-%237c3aed" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/license-MIT-%237c3aed" alt="MIT License">
  <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-%237c3aed" alt="Platforms">
  <img src="https://img.shields.io/badge/cli-%E2%9C%A8%20ready-%237c3aed" alt="CLI">
</p>

---

## Install

**One command, any platform:**

```bash
# macOS, Linux, Termux
curl -fsSL https://raw.githubusercontent.com/Clioloop/Clioloop-agent/main/scripts/install.sh | bash
```

```powershell
# Windows PowerShell
iex (irm https://raw.githubusercontent.com/Clioloop/Clioloop-agent/main/scripts/install.ps1)
```

**Windows users** can also download [`Clio-Setup.exe`](https://github.com/Clioloop/Clioloop-agent/releases) — a GUI installer that handles everything.

After install:

```bash
clio                          # Launch interactive chat
clio desktop                  # Launch the desktop app
clio dashboard                # Launch the web dashboard
clio update                   # Update to the latest version
```

---

## Features

### ∞ Omni Loop Portal — one login, 300+ models
The fastest way to get running: pick **Omni Loop Portal** in `clio setup`, approve the
device code in your browser, and your agent gets every frontier model (Claude, GPT,
Gemini, Grok, DeepSeek, …) through a single subscription — no API keys to manage.
Works across the CLI, TUI, desktop app, and web dashboard. Plans start free
(card verification only). The portal itself lives in [`portal/`](portal/) and is
self-hostable: `cd portal && npm run setup && npm run dev`.

### AI-Native Agent Loop
Full-featured agent with tool calls, multi-turn conversations, context management, and support for **OpenAI**, **Anthropic**, **Google Gemini**, **Groq**, **OpenRouter**, and any OpenAI-compatible endpoint.

### Skills That Self-Improve
Clioloop doesn't just run — it learns. The agent detects repeated work patterns and generates reusable skills from them. Skills improve during use and can be shared via the Skills Hub.

### Terminal-Native
Built for the command line. The TUI (terminal UI) provides a rich chat experience with markdown rendering, syntax-highlighted code blocks, inline images, and session management — all inside your terminal.

### Multi-Surface
| Surface | Command | Description |
|---|---|---|
| Terminal TUI | `clio` | Full-featured terminal chat UI |
| Desktop App | `clio desktop` | Electron-based GUI with system tray |
| Web Dashboard | `clio dashboard` | Browser-based management interface |
| Headless API | `clio gateway` | REST/WebSocket API for integrations |
| Slack Bot | `clio slack` | Chat with Clioloop from Slack |
| Telegram Bot | `clio gateway` | Telegram integration via the gateway |
| WhatsApp | `clio whatsapp` | WhatsApp messaging support |
| VS Code | `clio lsp` | LSP-powered editor integration |

### Platform & Provider Plugins
Swap models and providers at runtime:
```bash
clio -m gpt-4o                     # OpenAI
clio -m claude-sonnet-4-20250514   # Anthropic
clio -m gemini-2.5-pro             # Google
clio --provider openrouter          # Any OpenRouter model
```

### Built-In Tools
Web browsing, file operations, code execution (Python/JS/bash), image generation, audio transcription, browser automation, Discord, email, calendar, Jira, and more — all configurable per session.

### Memory & Context
Long-term memory via vector databases, session persistence with checkpoint/restore, cron-based scheduled tasks, and kanban-style project management.

### Security
SOC2-aware audit logging, PII redaction, credential scanning, file access controls, and a doctor command that validates your entire setup.

---

## Commands

| Command | Description |
|---|---|
| `clio` | Start an interactive chat session |
| `clio chat "message"` | One-shot query (non-interactive) |
| `clio acp "task"` | Agent Communication Protocol — autonomous task execution |
| `clio auth` | Manage API keys and provider credentials |
| `clio backup` | Backup your Clioloop configuration |
| `clio config` | View and edit configuration |
| `clio cron` | Schedule recurring agent tasks |
| `clio dashboard` | Launch the web dashboard |
| `clio desktop` | Launch the desktop GUI app |
| `clio doctor` | Diagnose installation and configuration issues |
| `clio gateway` | Start the REST API gateway |
| `clio gui` | Launch the Tauri-based installer |
| `clio kanban` | Kanban-style task management |
| `clio login` | Authenticate with providers |
| `clio mcp` | Model Context Protocol server |
| `clio memory` | Manage long-term memory stores |
| `clio model` | List and switch AI models |
| `clio plugins` | Manage plugins and integrations |
| `clio profile` | Switch between agent profiles/personas |
| `clio security` | Security audit and advisory checks |
| `clio setup` | First-run setup wizard |
| `clio skills` | Browse, install, and manage skills |
| `clio status` | Show system status and version info |
| `clio tools` | Configure available tool sets |
| `clio uninstall` | Remove Clioloop from your system |
| `clio update` | Update to the latest version |
| `clio version` | Print version information |

---

## Development

```bash
# Clone and set up
git clone https://github.com/Clioloop/Clioloop-agent.git
cd clioloop-agent

# Python dependencies (uv recommended)
uv sync --all-extras --dev

# Node dependencies (for desktop, TUI, and web)
npm install

# Run from source
uv run clio --help

# Run tests
npm -w ui-tui test                    # Terminal UI tests
uv run pytest tests/                  # Python test suite

# Build desktop app
npm -w apps/desktop run build

# Build Windows installer
npm -w apps/bootstrap-installer run tauri:build
```

---

## Architecture

```
clioloop-agent/
├── clio_cli/              # CLI frontend & Python agent core
├── apps/
│   ├── desktop/           # Electron desktop GUI
│   ├── bootstrap-installer/  # Tauri Windows installer
│   └── ...                # Other app surfaces
├── ui-tui/                # Terminal UI (React Ink)
├── web/                   # Web dashboard (React)
├── agent/                 # Agent runtime & tool execution
├── gateway/               # REST/WebSocket API gateway
├── acp_registry/          # Agent Communication Protocol registry
├── tools/                 # Built-in tool implementations
├── scripts/               # Install scripts for all platforms
├── docs/                  # Documentation
└── tests/                 # Test suite
```

---

## License

MIT. See [LICENSE](LICENSE).

<p align="center">
  <sub>Built by <a href="https://github.com/Clioloop">Omni Loop Labs</a></sub>
</p>
