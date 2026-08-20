# Clio Desktop UI tools

Clio Desktop sessions receive a private `desktop_ui` toolset. The tool schemas
are never exposed to CLI, cron, or messaging sessions, so non-GUI turns pay no
prompt cost and cannot accidentally target a desktop window.

Tools:

- `open_preview` / `close_preview` — open or dismiss the current window's preview.
- `read_preview` — return the active preview identity and bounded rendered text when available.
- `read_terminal` / `close_terminal` — inspect the visible terminal buffer or hide its pane without killing the shell process.
- `focus_pane` — reveal chat, sessions, files, preview, review, or terminal.
- `apply_layout` — apply a bounded pane preset (`default`, `focus`, `coding`, `review`, `research`).
- `tour` — discover targetable controls and show/start/stop an in-app guided tour.
- `react_to_message` — request a local message reaction when the renderer supports it.
- `read_window_below` — request metadata for the OS window underneath Clio; unsupported platforms return a truthful unavailable result.

## Routing and security

The Electron backend sets `CLIO_DESKTOP=1` only on desktop-managed backend
processes. The TUI gateway adds the toolset and assigns each active renderer a
`CLIO_UI_SESSION_ID` ContextVar. Tool actions are emitted to that exact runtime
session; they never use a process-global "last window" pointer.

Read operations use a bounded request/reply protocol (`desktop_ui.request` /
`desktop_ui.respond`) with an eight-second tool timeout. Renderer absence,
window closure, and unsupported OS capabilities fail closed.
