#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/Library/WindSentinel"
BIN_DIR="$ROOT_DIR/bin"
CONFIG_DIR="$ROOT_DIR/config"
LOG_DIR="$ROOT_DIR/logs"
STATE_DIR="$ROOT_DIR/state"
LAUNCHD_PLIST_SRC="$(cd "$(dirname "$0")" && pwd)/com.windsentinel.agent.plist"
LAUNCHD_PLIST_DST="/Library/LaunchDaemons/com.windsentinel.agent.plist"
AGENT_SRC="${1:-}"
CONFIG_SRC="${2:-}"

if [[ -z "$AGENT_SRC" || -z "$CONFIG_SRC" ]]; then
  echo "Usage: $0 <agent-binary> <signed-config.json>" >&2
  exit 1
fi

mkdir -p "$BIN_DIR" "$CONFIG_DIR" "$LOG_DIR" "$STATE_DIR"
install -m 0755 "$AGENT_SRC" "$BIN_DIR/windsentinel_agent"
install -m 0644 "$CONFIG_SRC" "$CONFIG_DIR/config.json"
install -m 0644 "$LAUNCHD_PLIST_SRC" "$LAUNCHD_PLIST_DST"
launchctl unload "$LAUNCHD_PLIST_DST" >/dev/null 2>&1 || true
launchctl load -w "$LAUNCHD_PLIST_DST"
launchctl kickstart -k system/com.windsentinel.agent || true

echo "WindSentinel agent installed to $ROOT_DIR"
echo "launchd plist: $LAUNCHD_PLIST_DST"
