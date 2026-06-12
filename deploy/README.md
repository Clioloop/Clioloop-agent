# Deployment

Production: Hetzner CX23 (`clioloop-portal`, nbg1) behind Caddy (auto-HTTPS) at
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
