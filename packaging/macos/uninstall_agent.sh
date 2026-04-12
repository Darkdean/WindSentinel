#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/Library/WindSentinel"
LAUNCHD_PLIST_DST="/Library/LaunchDaemons/com.windsentinel.agent.plist"

launchctl bootout system/com.windsentinel.agent >/dev/null 2>&1 || true
launchctl unload "$LAUNCHD_PLIST_DST" >/dev/null 2>&1 || true
rm -f "$LAUNCHD_PLIST_DST"
rm -rf "$ROOT_DIR"

echo "WindSentinel agent removed from macOS launchd path"
