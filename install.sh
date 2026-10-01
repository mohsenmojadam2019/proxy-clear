#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
TARGET_USER="${PROXY_CLEAR_USER:-${SUDO_USER:-${USER}}}"
if [[ "$TARGET_USER" == "root" || "$TARGET_USER" == "sentinelx" ]]; then
  TARGET_USER="${PROXY_CLEAR_USER:-god}"
fi
TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"
if [[ -z "$TARGET_HOME" ]]; then
  echo "Cannot resolve home for user: $TARGET_USER" >&2
  exit 1
fi

if [[ "$EUID" -ne 0 ]]; then
  exec sudo PROXY_CLEAR_USER="$TARGET_USER" "$0" "$@"
fi

runuser -u "$TARGET_USER" -- python3 "$ROOT/scripts/build.py" >/tmp/proxy-clear-build.json
EXT_ID="$(tr -d '\n' < "$ROOT/dist/extension-id.txt")"

USER_LIB="$TARGET_HOME/.local/lib/proxy-clear"
install -d -m 0755 -o "$TARGET_USER" -g "$TARGET_USER" "$USER_LIB"
install -m 0755 -o "$TARGET_USER" -g "$TARGET_USER" "$ROOT/native/native_helper.py" "$USER_LIB/native_helper.py"

SYS_DIR="/usr/local/lib/proxy-clear"
install -d -m 0755 -o root -g root "$SYS_DIR"
install -m 0755 -o root -g root "$ROOT/native/system_clear.py" "$SYS_DIR/system_clear.py"

SUDOERS="/etc/sudoers.d/proxy-clear"
cat > "$SUDOERS" <<EOF
$TARGET_USER ALL=(root) NOPASSWD: $SYS_DIR/system_clear.py --scan --json
$TARGET_USER ALL=(root) NOPASSWD: $SYS_DIR/system_clear.py --clear --json
EOF
chmod 0440 "$SUDOERS"
visudo -cf "$SUDOERS" >/dev/null

CHROME_HOST_DIR="$TARGET_HOME/.config/google-chrome/NativeMessagingHosts"
CHROMIUM_HOST_DIR="$TARGET_HOME/.config/chromium/NativeMessagingHosts"
FIREFOX_HOST_DIR="$TARGET_HOME/.mozilla/native-messaging-hosts"

for DIR in "$CHROME_HOST_DIR" "$CHROMIUM_HOST_DIR"; do
  install -d -m 0755 -o "$TARGET_USER" -g "$TARGET_USER" "$DIR"
  cat > "$DIR/com.proxyclear.helper.json" <<EOF
{
  "name": "com.proxyclear.helper",
  "description": "Proxy Clear native helper",
  "path": "$USER_LIB/native_helper.py",
  "type": "stdio",
  "allowed_origins": ["chrome-extension://$EXT_ID/"]
}
EOF
  chown "$TARGET_USER:$TARGET_USER" "$DIR/com.proxyclear.helper.json"
  chmod 0644 "$DIR/com.proxyclear.helper.json"
done

install -d -m 0755 -o "$TARGET_USER" -g "$TARGET_USER" "$FIREFOX_HOST_DIR"
cat > "$FIREFOX_HOST_DIR/com.proxyclear.helper.json" <<EOF
{
  "name": "com.proxyclear.helper",
  "description": "Proxy Clear native helper",
  "path": "$USER_LIB/native_helper.py",
  "type": "stdio",
  "allowed_extensions": ["proxy-clear@local"]
}
EOF
chown "$TARGET_USER:$TARGET_USER" "$FIREFOX_HOST_DIR/com.proxyclear.helper.json"
chmod 0644 "$FIREFOX_HOST_DIR/com.proxyclear.helper.json"

chown -R "$TARGET_USER:$TARGET_USER" "$ROOT"
echo "Installed Proxy Clear for $TARGET_USER"
echo "Chrome extension ID: $EXT_ID"
echo "Chrome unpacked path: $ROOT/dist/chrome"
echo "Firefox unpacked path: $ROOT/dist/firefox"
