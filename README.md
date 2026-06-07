# Clioloop Agent

Clioloop is a self-improving AI agent by Omni Loop Labs. It runs from the terminal, desktop app, or web dashboard, uses model-provider plugins, and can grow new skills from repeated work.

## Install

macOS, Linux, and Termux:

```bash
curl -fsSL https://raw.githubusercontent.com/Clioloop/Clioloop-agent/main/scripts/install.sh | bash
```

Windows PowerShell:

```powershell
iex (irm https://raw.githubusercontent.com/Clioloop/Clioloop-agent/main/scripts/install.ps1)
```

Private-repo installs can pass a GitHub token:

```powershell
iex "& { $(irm https://raw.githubusercontent.com/Clioloop/Clioloop-agent/main/scripts/install.ps1) } -GitHubToken ghp_your_token"
```

## Run

```bash
clio
clio desktop
clio dashboard
```

## Update

```bash
clio update
```

## Development

```bash
uv sync --all-extras --dev
npm install
uv run clio --help
npm -w ui-tui test
npm -w apps/desktop run build
```

The Windows desktop installer is built from `apps/bootstrap-installer` and the Electron desktop app is built from `apps/desktop`.

## License

MIT. See [LICENSE](LICENSE).
