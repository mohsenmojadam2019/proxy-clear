#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
MODE="${1:-chrome}"
EXT_ID="$(tr -d '\n' < "$ROOT/dist/extension-id.txt")"

export DISPLAY="${DISPLAY:-:0}"
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=/run/user/$(id -u)/bus}"
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"

if [[ "$MODE" == "chrome" ]]; then
  DEV_BROWSER=""
  for CANDIDATE in chromium chromium-browser chrome-for-testing; do
    if command -v "$CANDIDATE" >/dev/null 2>&1; then
      DEV_BROWSER="$(command -v "$CANDIDATE")"
      break
    fi
  done

  if [[ -n "$DEV_BROWSER" ]]; then
    nohup "$DEV_BROWSER" \
      --load-extension="$ROOT/dist/chrome" \
      --new-window "chrome-extension://$EXT_ID/popup.html" \
      >"$ROOT/dist/chrome-launch.log" 2>&1 &
    echo $! > "$ROOT/dist/chrome-launch.pid"
    echo "Proxy Clear launched in: $DEV_BROWSER"
    exit 0
  fi

  CHROME="$(command -v google-chrome || command -v google-chrome-stable || true)"
  [[ -n "$CHROME" ]] || { echo "Chrome/Chromium not found" >&2; exit 1; }

  nohup "$CHROME" --new-window "chrome://extensions/" >"$ROOT/dist/chrome-launch.log" 2>&1 &
  if command -v xdg-open >/dev/null 2>&1; then
    nohup xdg-open "$ROOT/dist/chrome" >/dev/null 2>&1 &
  fi

  echo "Official Google Chrome no longer accepts --load-extension on current branded builds."
  echo "Developer mode -> Load unpacked -> $ROOT/dist/chrome"
  exit 0
fi

if [[ "$MODE" == "firefox" ]]; then
  if command -v web-ext >/dev/null 2>&1; then
    nohup web-ext run --source-dir "$ROOT/dist/firefox" --firefox /usr/bin/firefox \
      >"$ROOT/dist/firefox-launch.log" 2>&1 &
    echo $! > "$ROOT/dist/firefox-launch.pid"
    echo "Firefox launched through web-ext."
  else
    nohup npx --yes web-ext@latest run \
      --source-dir "$ROOT/dist/firefox" \
      --firefox=/usr/bin/firefox \
      --no-input \
      >"$ROOT/dist/firefox-launch.log" 2>&1 &
    echo $! > "$ROOT/dist/firefox-launch.pid"
    echo "Firefox launched through npx web-ext."
  fi
  exit 0
fi

echo "Usage: $0 [chrome|firefox]" >&2
exit 1
