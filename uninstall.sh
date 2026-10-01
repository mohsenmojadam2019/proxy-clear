#!/usr/bin/env bash
set -euo pipefail
TARGET_USER="${PROXY_CLEAR_USER:-${SUDO_USER:-${USER}}}"
if [[ "$TARGET_USER" == "root" || "$TARGET_USER" == "sentinelx" ]]; then
  TARGET_USER="${PROXY_CLEAR_USER:-god}"
fi
TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"
if [[ "$EUID" -ne 0 ]]; then
  exec sudo PROXY_CLEAR_USER="$TARGET_USER" "$0" "$@"
fi
rm -f "$TARGET_HOME/.config/google-chrome/NativeMessagingHosts/com.proxyclear.helper.json"
rm -f "$TARGET_HOME/.config/chromium/NativeMessagingHosts/com.proxyclear.helper.json"
rm -f "$TARGET_HOME/.mozilla/native-messaging-hosts/com.proxyclear.helper.json"
rm -rf "$TARGET_HOME/.local/lib/proxy-clear"
rm -rf /usr/local/lib/proxy-clear
rm -f /etc/sudoers.d/proxy-clear
echo "Proxy Clear native integration removed."
