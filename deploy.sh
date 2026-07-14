#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# DailyDex — Fresh VM Deploy Script
# Works on Ubuntu 22.04/24.04. Run as root or sudo user.
#
# Usage:
#   git clone https://github.com/amonkarsidhant/DailyDex.git
#   cd DailyDex
#   cp .env.example .env  # fill in your keys
#   bash deploy.sh
# ============================================================

echo "=========================================="
echo "  DailyDex VM Deploy"
echo "=========================================="

# ── 1. Install Docker + Docker Compose ──────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "Installing Docker..."
    apt-get update -y
    apt-get install -y ca-certificates curl gnupg
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list
    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    systemctl enable --now docker
    usermod -aG docker "${SUDO_USER:-$USER}" 2>/dev/null || true
    echo "  Docker installed."
else
    echo "  Docker already installed — skipping."
fi

# ── 2. Verify .env exists ───────────────────────────────────────────────────
if [ ! -f .env ]; then
    echo "ERROR: .env file not found."
    echo "  Run: cp .env.example .env"
    echo "  Then edit .env with your API keys."
    exit 1
fi

if grep -qE "^NOTION_API_TOKEN=$" .env 2>/dev/null; then
    echo "WARNING: NOTION_API_TOKEN is empty in .env — Notion sync will be skipped."
fi

if grep -qE "^NVIDIA_API_KEY=$" .env 2>/dev/null; then
    echo "WARNING: NVIDIA_API_KEY is empty in .env — LLM enrichment will fail."
fi

# ── 3. Build and start ──────────────────────────────────────────────────────
echo "Building Docker images..."
docker compose build

echo "Starting services..."
docker compose up -d

# ── 4. Wait for health check ────────────────────────────────────────────────
echo "Waiting for web app to become healthy..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:8888/health >/dev/null 2>&1; then
        echo "  Web app is healthy!"
        break
    fi
    sleep 2
    if [ $i -eq 30 ]; then
        echo "ERROR: Web app did not become healthy in 60s."
        docker compose logs --tail 50 web
        exit 1
    fi
done

# ── 5. Show status ──────────────────────────────────────────────────────────
echo ""
echo "=========================================="
echo "  Deploy complete!"
echo "=========================================="
echo ""
echo "  Web app:       http://$(hostname -I | awk '{print $1}'):8888"
echo "  Cockpit:       http://$(hostname -I | awk '{print $1}'):8888/cockpit"
echo "  Health:        http://$(hostname -I | awk '{print $1}'):8888/health"
echo ""
echo "  Containers:"
docker compose ps
echo ""
echo "  Orchestrator logs:"
echo "    docker compose logs -f orchestrator"
echo ""
echo "  To stop:"
echo "    docker compose down"
echo ""
echo "  To update (pull latest + restart):"
echo "    git pull && docker compose build && docker compose up -d"
echo ""