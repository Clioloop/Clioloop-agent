#!/bin/bash
# Provision clioloop-portal: Node 22, Caddy, portal app under systemd.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

echo "── base packages"
apt-get update -q
apt-get install -yq curl git ca-certificates gnupg build-essential python3 unattended-upgrades

echo "── node 22"
if ! command -v node >/dev/null; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -yq nodejs
fi
node --version

echo "── caddy"
if ! command -v caddy >/dev/null; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -q && apt-get install -yq caddy
fi

echo "── app user + checkout"
id -u portal &>/dev/null || useradd -m -s /bin/bash portal
if [ ! -d /home/portal/app ]; then
  sudo -u portal git clone --depth 1 https://github.com/Clioloop/Clioloop-agent.git /home/portal/app
else
  sudo -u portal git -C /home/portal/app pull --ff-only
fi

echo "── overlay private Fusion engine"
# The Fusion engine (prompts + pipeline) lives in the private repo
# Clioloop/Clioloop-fusion and is NEVER in the public repo (see .gitignore). It
# is overlaid into the portal tree here before the build so the /api/v1/fusion
# routes exist on the server only. Requires a read-only GitHub deploy key at
# /home/portal/.ssh/fusion_deploy (add its .pub as a deploy key on the private
# repo). If the key/repo is unavailable the build still succeeds — the agent's
# thin client degrades gracefully (404 → normal turn).
FUSION_DEPLOY_KEY=/home/portal/.ssh/fusion_deploy
FUSION_LIB=/home/portal/app/portal/src/lib/fusion
FUSION_API=/home/portal/app/portal/src/app/api/v1/fusion
if [ -f "$FUSION_DEPLOY_KEY" ]; then
  rm -rf /tmp/clioloop-fusion
  if sudo -u portal env GIT_SSH_COMMAND="ssh -i $FUSION_DEPLOY_KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new" \
      git clone --depth 1 git@github.com:Clioloop/Clioloop-fusion.git /tmp/clioloop-fusion; then
    sudo -u portal mkdir -p "$FUSION_LIB" "$FUSION_API"
    sudo -u portal cp -r /tmp/clioloop-fusion/lib/. "$FUSION_LIB"/
    sudo -u portal cp -r /tmp/clioloop-fusion/api/. "$FUSION_API"/
    echo "   fusion engine overlaid"
  else
    echo "   WARN: could not clone Clioloop-fusion — building without server-side Fusion"
  fi
  rm -rf /tmp/clioloop-fusion
else
  echo "   WARN: $FUSION_DEPLOY_KEY missing — building without server-side Fusion"
fi

echo "── build portal"
cd /home/portal/app/portal
sudo -u portal npm ci --no-audit --no-fund
sudo -u portal npm run build

echo "── env file"
if [ ! -f /home/portal/portal.env ]; then
  SESSION_SECRET=$(openssl rand -hex 32)
  cat > /home/portal/portal.env <<EOF
NODE_ENV=production
HOST=127.0.0.1
PORT=4280
PORTAL_BASE_URL=https://portal.clioloop.com
SESSION_SECRET=${SESSION_SECRET}
PORTAL_DATA_DIR=/home/portal/data
OPENROUTER_API_KEY=__OPENROUTER__
FIRECRAWL_API_KEY=__FIRECRAWL__
BROWSER_USE_API_KEY=__BROWSERUSE__
STRIPE_SECRET_KEY=__STRIPE_SK__
STRIPE_WEBHOOK_SECRET=__STRIPE_WH__
STRIPE_PRICE_PRO=__PRICE_PRO__
STRIPE_PRICE_MAX=__PRICE_MAX__
STRIPE_PRICE_MAX20X=__PRICE_MAX20X__
EOF
  chown portal:portal /home/portal/portal.env
  chmod 600 /home/portal/portal.env
fi
sudo -u portal mkdir -p /home/portal/data

echo "── systemd unit"
cat > /etc/systemd/system/portal.service <<'EOF'
[Unit]
Description=Omni Loop Portal (Next.js)
After=network-online.target
Wants=network-online.target

[Service]
User=portal
WorkingDirectory=/home/portal/app/portal
EnvironmentFile=/home/portal/portal.env
ExecStart=/usr/bin/npm start
Restart=always
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

echo "── caddy config"
cat > /etc/caddy/Caddyfile <<'EOF'
portal.clioloop.com {
	encode gzip
	reverse_proxy 127.0.0.1:4280
}

clioloop.com, www.clioloop.com {
	redir https://portal.clioloop.com{uri} permanent
}
EOF

systemctl daemon-reload
systemctl enable --now portal
systemctl reload caddy || systemctl restart caddy
echo "── done"
