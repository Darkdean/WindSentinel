#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <agent-binary> <signed-config.json> [output-pkg]" >&2
  exit 1
fi

AGENT_SRC="$1"
CONFIG_SRC="$2"
VERSION="${WINDSENTINEL_PKG_VERSION:-$(cat VERSION 2>/dev/null || echo v1.0)}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKDIR="$(mktemp -d /tmp/windsentinel-pkg.XXXXXX)"
ROOT="$WORKDIR/root"
SCRIPTS="$WORKDIR/scripts"
APP_DIR="$ROOT/Applications/WindSentinel Uninstall.app"
UNINSTALL_EXE="$APP_DIR/Contents/MacOS/WindSentinel Uninstall"
INFO_PLIST="$APP_DIR/Contents/Info.plist"
LAUNCHD_DST="$ROOT/Library/LaunchDaemons/com.windsentinel.agent.plist"
TARGET_OS="macos"
TARGET_VERSION="${WINDSENTINEL_TARGET_VERSION:-$(sw_vers -productVersion 2>/dev/null | cut -d. -f1)}"
RAW_ARCH="${WINDSENTINEL_TARGET_ARCH:-$(uname -m)}"
case "$RAW_ARCH" in
  arm64) TARGET_ARCH="aarch64" ;;
  aarch64) TARGET_ARCH="aarch64" ;;
  i386) TARGET_ARCH="x86_64" ;;
  x86_64) TARGET_ARCH="x86_64" ;;
  *) TARGET_ARCH="$RAW_ARCH" ;;
esac
OUTPUT_PKG="${3:-$(pwd)/installPack/${TARGET_OS}/${TARGET_VERSION}/${TARGET_ARCH}/WindSentinel-Agent.pkg}"
VERIFY_KEY_B64="$(python3 - <<'PY' "$CONFIG_SRC"
import json, sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text())
config = data.get('config') or {}
print(config.get('shared_key_b64', ''))
PY
)"

mkdir -p "$ROOT/Library/WindSentinel/bin" "$ROOT/Library/WindSentinel/config" "$ROOT/Library/WindSentinel/logs" "$ROOT/Library/WindSentinel/state"
mkdir -p "$ROOT/Library/LaunchDaemons" "$APP_DIR/Contents/MacOS"
mkdir -p "$SCRIPTS"
mkdir -p "$(dirname "$OUTPUT_PKG")"

install -m 0755 "$AGENT_SRC" "$ROOT/Library/WindSentinel/bin/windsentinel_agent"
install -m 0644 "$CONFIG_SRC" "$ROOT/Library/WindSentinel/config/config.json"
sed "s#__VERIFY_KEY_B64__#$VERIFY_KEY_B64#g" "$SCRIPT_DIR/com.windsentinel.agent.plist" > "$LAUNCHD_DST"
chmod 0644 "$LAUNCHD_DST"

cat > "$UNINSTALL_EXE" <<'APP'
#!/bin/bash
set -euo pipefail
AGENT="/Library/WindSentinel/bin/windsentinel_agent"
CONFIG="/Library/WindSentinel/config/config.json"
STATE="/Library/WindSentinel/state"
CODE=$(osascript -e 'text returned of (display dialog "请输入离线卸载码" default answer "" with title "WindSentinel 卸载")')
if [[ -z "$CODE" ]]; then
  exit 1
fi
env WINDSENTINEL_AGENT_CONFIG_PATH="$CONFIG" WINDSENTINEL_AGENT_STATE_DIR="$STATE" "$AGENT" control uninstall --code "$CODE"
APP
chmod 0755 "$UNINSTALL_EXE"

cat > "$INFO_PLIST" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>CFBundleExecutable</key>
    <string>WindSentinel Uninstall</string>
    <key>CFBundleIdentifier</key>
    <string>com.windsentinel.uninstall</string>
    <key>CFBundleName</key>
    <string>WindSentinel Uninstall</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
  </dict>
</plist>
PLIST

install -m 0755 "$SCRIPT_DIR/scripts/preinstall" "$SCRIPTS/preinstall"
install -m 0755 "$SCRIPT_DIR/scripts/postinstall" "$SCRIPTS/postinstall"

pkgbuild \
  --root "$ROOT" \
  --scripts "$SCRIPTS" \
  --identifier com.windsentinel.agent \
  --version "$VERSION" \
  "$OUTPUT_PKG"

echo "$OUTPUT_PKG"
