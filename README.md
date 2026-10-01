# Proxy Clear

Proxy Clear is a local WebExtension + Linux native helper that disables and removes common proxy settings from Chrome/Chromium, Firefox and Ubuntu/Linux system layers.

## What it clears

- Chrome/Chromium proxy mode via the browser Proxy API (`direct`)
- Firefox proxy mode via the browser Proxy API (`none`)
- GNOME proxy mode plus stale HTTP/HTTPS/FTP/SOCKS host and port values
- User proxy environment assignments in common shell/environment files
- Git global `http.proxy` and `https.proxy`
- systemd user proxy environment variables
- `/etc/environment`, `/etc/profile`, `/etc/bash.bashrc`, `/etc/profile.d/*.sh`
- APT proxy directives
- system Git proxy settings
- systemd manager proxy environment variables
- Snap proxy settings
- `/etc/wgetrc` and `/etc/curlrc`

System file edits are backed up under `/var/backups/proxy-clear/<timestamp>/`. User file edits are backed up under `~/.local/state/proxy-clear/backups/<timestamp>/`.

## Architecture

Browser extensions cannot directly edit Linux system configuration. Proxy Clear uses native messaging. The extension clears browser proxy state, a user helper clears per-user settings, and a narrowly scoped root helper clears known system proxy settings.

## Build

```bash
python3 scripts/build.py
```

Outputs: `dist/chrome/`, `dist/firefox/`, `proxy-clear-chrome.zip`, and `proxy-clear-firefox.xpi`.

## Install

```bash
sudo PROXY_CLEAR_USER="$USER" ./install.sh
```

## Launch

```bash
./launch.sh chrome
./launch.sh firefox
```

On current official Google Chrome builds, command-line loading of unpacked extensions is blocked. `./launch.sh chrome` therefore opens `chrome://extensions/` and the unpacked build folder so it can be loaded with **Developer mode → Load unpacked**. Chromium / Chrome for Testing builds are loaded automatically when available.

Firefox development launch uses `web-ext` and installs the extension into a temporary Firefox profile automatically.

## Limits

Enterprise browser policies and proxy command-line flags can be non-controllable by an extension. The popup reports the browser control state. Firefox stable requires a signed XPI for permanent distribution; the included `web-ext` launch is intended for local development/testing.
