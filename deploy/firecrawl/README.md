# Self-hosted Firecrawl (web search + extract) for the Omni Loop Portal

Replaces the paid Firecrawl cloud API (`api.firecrawl.dev`) with a self-hosted
Firecrawl + SearXNG stack on the portal box. The portal's `firecrawl` gateway
vendor (`portal/src/lib/gateway.ts`) proxies to it via `FIRECRAWL_UPSTREAM_URL`
— same self-host pattern as Supertonic TTS. Web search/extract is gated to
**Pro and up** (`portal/src/lib/plans.ts`: `free.services` excludes `"web"`).

Runs the current upstream Firecrawl stack (api + Playwright + Redis + RabbitMQ +
nuq-postgres + FoundationDB) from **prebuilt GHCR images** (no source build),
plus a private **SearXNG** for `/v2/search`. Everything binds to localhost.

Deployed live 2026-06-15 on the resized box (cx43, 8 vCPU / 16 GB).

## 1. Box prep (one-time)

```bash
export HCLOUD_TOKEN=...; SERVER=clioloop-portal
# Safety snapshot, then CPU/RAM-only rescale (keep disk, reversible). ~1-3 min downtime.
hcloud server create-image --type snapshot --description "pre-firecrawl" $SERVER
hcloud server poweroff $SERVER && hcloud server change-type --keep-disk $SERVER cx43 && hcloud server poweron $SERVER
# 4 GB swap cushion + Docker:
ssh root@portal.clioloop.com '
  fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile &&
  grep -q /swapfile /etc/fstab || echo "/swapfile none swap sw 0 0" >> /etc/fstab
  command -v docker >/dev/null || curl -fsSL https://get.docker.com | sh'
```

## 2. Lay down the stack

```bash
ssh root@portal.clioloop.com '
  git clone --depth 1 https://github.com/firecrawl/firecrawl.git /opt/firecrawl
  D=/home/portal/app/deploy/firecrawl   # this dir (from the portal app checkout)
  cp $D/firecrawl.env.example            /opt/firecrawl/.env
  cp $D/docker-compose.override.local.yml /opt/firecrawl/
  sed "s/REPLACE_WITH_RANDOM_HEX/$(openssl rand -hex 32)/" $D/searxng-settings.yml > /opt/firecrawl/searxng-settings.yml
  cp $D/firecrawl.service /etc/systemd/system/firecrawl.service
  systemctl daemon-reload && systemctl enable firecrawl'
```

## 3. Bring it up (prebuilt images, localhost-only)

```bash
ssh root@portal.clioloop.com 'cd /opt/firecrawl
  docker compose -f docker-compose.yaml -f docker-compose.override.local.yml pull
  docker compose -f docker-compose.yaml -f docker-compose.override.local.yml up -d --no-build
  docker compose -f docker-compose.yaml -f docker-compose.override.local.yml ps'
```

## 4. Point the portal at it (no portal code change)

Append to `/home/portal/portal.env`, then redeploy:
```
FIRECRAWL_UPSTREAM_URL=http://127.0.0.1:3002
FIRECRAWL_API_KEY=selfhosted        # any non-empty value; self-host ignores it
```
```bash
ssh root@portal.clioloop.com 'sudo -u portal git -C /home/portal/app pull
  && cd /home/portal/app/portal && sudo -u portal npm ci && sudo -u portal npm run build
  && systemctl restart portal'
```

## 5. Verify

```bash
# Stack (on the box): scrape + search return data, localhost-only.
ssh root@server 'curl -s -X POST 127.0.0.1:3002/v2/scrape -H "content-type: application/json" \
  -d "{\"url\":\"https://example.com\",\"formats\":[\"markdown\"]}" | head -c 200
  curl -s -X POST 127.0.0.1:3002/v2/search -H "content-type: application/json" \
  -d "{\"query\":\"test\",\"limit\":3}" | head -c 200
  ss -ltnp | grep 3002   # must be 127.0.0.1:3002 only'
# Portal gateway is live + auth-gated (no token -> 401):
curl -s -X POST https://portal.clioloop.com/api/gateway/firecrawl/v2/search -d "{}"  # {"error":"invalid_token"}
# End-to-end: a Pro/Max agent web_search lands on the api ("Using searxng search"):
ssh root@server 'cd /opt/firecrawl && docker compose -f docker-compose.yaml -f docker-compose.override.local.yml logs --since 5m api | grep searchController'
```
- Free account: `/api/account/info` shows `web:false`; gateway 403 `plan_upgrade_required`.

## Notes
- Only `127.0.0.1:3002` is published; all other services are internal to the
  Docker `backend` network. Never expose 3002 publicly (auth is disabled).
- Tune `NUM_WORKERS_PER_QUEUE` / `MAX_CONCURRENT_JOBS` (`.env`) and the api
  `cpus`/`mem_limit` (upstream compose) for more concurrency; keep ~4 GB free for
  the portal + Supertonic (the swap is a cushion, not a substitute).
- SearXNG tolerates per-engine failures (it logs tracebacks for engines that
  rate-limit/timeout); disable flaky engines in `searxng-settings.yml` if needed.
