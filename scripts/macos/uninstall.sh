#!/bin/bash
# Remove the DailyDex Cockpit LaunchAgents (leaves the venv and data intact).
set -euo pipefail

AGENTS_DIR="$HOME/Library/LaunchAgents"
DOMAIN="gui/$(id -u)"

for label in com.dailydex.app com.dailydex.refresh; do
    echo "==> removing $label"
    launchctl bootout "$DOMAIN/$label" 2>/dev/null || true
    rm -f "$AGENTS_DIR/$label.plist"
done

echo "Uninstalled. Data and venv kept; delete .venv-cockpit and data/ manually if you want a clean wipe."
