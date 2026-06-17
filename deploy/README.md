# Deployment

Production: Hetzner cx43 (`clioloop-portal`, nbg1; resized from cx23 to host the
self-hosted Firecrawl stack) behind Caddy (auto-HTTPS) at
https://portal.clioloop.com (apex + www redirect there).

- `provision.sh` — idempotent server bootstrap: Node 22, Caddy, app user,
  clone/build, systemd unit (`portal.service`), Caddyfile. Secrets are
  injected into `/home/portal/portal.env` (chmod 600) after the first run.
- Backups: `/usr/local/bin/portal-backup` (cron 03:17 UTC) — SQLite `.backup`
  as the app user, 14 days retained locally, best-effort push to R2
  (`r2:clioloop-backups/portal/`).
- Redeploy after a push: `ssh root@server 'sudo -u portal git -C /home/portal/app pull
  && cd /home/portal/app/portal && sudo -u portal npm ci && sudo -u portal npm run build
  && systemctl restart portal'`

## Self-hosted tool-gateway vendors

The portal proxies bundled tool services to self-hosted upstreams via
`*_UPSTREAM_URL` env vars (no portal code change; see `portal/src/lib/gateway.ts`):

- **TTS** — `supertonic_server.py` (`openai-audio`, `:8077`).
- **Web search + extract** — self-hosted Firecrawl + SearXNG, gated to Pro+.
  Full runbook (resize, swap, Docker, stack, cutover, verify) in
  [`deploy/firecrawl/README.md`](firecrawl/README.md). Set
  `FIRECRAWL_UPSTREAM_URL=http://127.0.0.1:3002` in `/home/portal/portal.env`.
