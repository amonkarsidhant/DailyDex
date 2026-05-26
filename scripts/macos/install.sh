#!/bin/bash
# Install DailyDex Cockpit as an always-on local macOS app.
#
#   - builds a local venv (.venv-cockpit) and installs requirements
#   - installs two LaunchAgents:
#       com.dailydex.app      -> Flask server on http://127.0.0.1:8888 (KeepAlive)
#       com.dailydex.refresh  -> hourly fetch/score/snapshot
#
# Re-running is safe: it reloads both agents.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
AGENTS_DIR="$HOME/Library/LaunchAgents"
DOMAIN="gui/$(id -u)"
PORT="${PORT:-8888}"

echo "DailyDex install"
echo "  app dir : $APP_DIR"
echo "  port    : $PORT"

# 1. venv + deps
if [ ! -x "$APP_DIR/.venv-cockpit/bin/python" ]; then
    echo "==> creating venv .venv-cockpit"
    python3 -m venv "$APP_DIR/.venv-cockpit"
fi
echo "==> installing requirements"
"$APP_DIR/.venv-cockpit/bin/pip" install -q --upgrade pip
"$APP_DIR/.venv-cockpit/bin/pip" install -q -r "$APP_DIR/requirements.txt"

mkdir -p "$APP_DIR/data/logs" "$AGENTS_DIR"

# 2. render + load each agent
render_and_load() {
    local label="$1"
    local src="$APP_DIR/scripts/macos/${label}.plist.template"
    local dst="$AGENTS_DIR/${label}.plist"
    echo "==> installing $label"
    sed "s#__APP_DIR__#$APP_DIR#g" "$src" > "$dst"
    plutil -lint "$dst" >/dev/null
    launchctl bootout "$DOMAIN/$label" 2>/dev/null || true
    # bootout is async — wait until the label is fully unloaded before reloading
    for _ in $(seq 1 10); do
        launchctl print "$DOMAIN/$label" >/dev/null 2>&1 || break
        sleep 0.5
    done
    launchctl bootstrap "$DOMAIN" "$dst"
}

render_and_load com.dailydex.app
render_and_load com.dailydex.refresh

# 3. wait for the server to answer
echo -n "==> waiting for http://127.0.0.1:$PORT "
for _ in $(seq 1 15); do
    if [ "$(curl -s -m2 -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/" 2>/dev/null)" = "200" ]; then
        echo "OK"
        break
    fi
    echo -n "."
    sleep 2
done

echo
echo "Installed. Open: http://127.0.0.1:$PORT"
echo "Logs:  $APP_DIR/data/logs/{app,refresh}.{out,err}.log"
echo "Manage: launchctl kickstart -k $DOMAIN/com.dailydex.app   # restart server now"
echo "        launchctl kickstart -p $DOMAIN/com.dailydex.refresh # refresh content now"
echo "Uninstall: scripts/macos/uninstall.sh"
