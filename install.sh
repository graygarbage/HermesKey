#!/usr/bin/env bash
set -euo pipefail

APP_ID="hermeskey"
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VERSION="$(tr -d '[:space:]' < "$ROOT/VERSION")"
BIN_DEST="$HOME/.local/bin"
SYSTEMD_DEST="$HOME/.config/systemd/user"
SHARE_DEST_DIR="${XDG_DATA_HOME:-$HOME/.local/share}"
APPLICATIONS_DEST="$SHARE_DEST_DIR/applications"
METADATA_DEST="$SHARE_DEST_DIR/metainfo"
CONFIG_DEST_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/$APP_ID"
DATA_DEST_DIR="$SHARE_DEST_DIR/$APP_ID"
ICON_THEME_DIR="$SHARE_DEST_DIR/icons/hicolor"
ICON_DEST="$ICON_THEME_DIR/scalable/apps"
CONFIG_DEST="$CONFIG_DEST_DIR/hermeskey.env"
CONFIG_EXAMPLE_DEST="$CONFIG_DEST_DIR/hermeskey.env.example"
VERSION_DEST="$DATA_DEST_DIR/VERSION"

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    printf 'Missing required command: %s\n' "$1" >&2
    exit 1
  }
}

warn_if_missing() {
  command -v "$1" >/dev/null 2>&1 || printf 'Warning: optional dependency not found: %s\n' "$1" >&2
}

need_cmd install
need_cmd systemctl
warn_if_missing ffmpeg
warn_if_missing wl-copy
warn_if_missing notify-send
warn_if_missing ydotool
warn_if_missing paplay

mkdir -p "$BIN_DEST" "$SYSTEMD_DEST" "$APPLICATIONS_DEST" "$METADATA_DEST" "$CONFIG_DEST_DIR" "$DATA_DEST_DIR" "$ICON_DEST"

install -m 0755 "$ROOT/bin/hermeskey" "$BIN_DEST/hermeskey"
install -m 0755 "$ROOT/bin/hermeskey-server.py" "$BIN_DEST/hermeskey-server.py"
install -m 0755 "$ROOT/bin/hermeskey-overlay.py" "$BIN_DEST/hermeskey-overlay.py"
install -m 0755 "$ROOT/bin/hermeskey-doctor" "$BIN_DEST/hermeskey-doctor"
install -m 0755 "$ROOT/bin/hermeskey-desktop-status" "$BIN_DEST/hermeskey-desktop-status"
install -m 0755 "$ROOT/bin/hermeskey-desktop-doctor" "$BIN_DEST/hermeskey-desktop-doctor"
install -m 0755 "$ROOT/bin/hermeskey-open-config" "$BIN_DEST/hermeskey-open-config"
install -m 0755 "$ROOT/bin/hermeskey-open-logs" "$BIN_DEST/hermeskey-open-logs"
install -m 0755 "$ROOT/bin/hermeskey-restart-services" "$BIN_DEST/hermeskey-restart-services"
install -m 0755 "$ROOT/bin/hermeskey-control-center" "$BIN_DEST/hermeskey-control-center"
install -m 0755 "$ROOT/bin/hermeskey-settings.py" "$BIN_DEST/hermeskey-settings.py"
install -m 0644 "$ROOT/systemd/user/hermeskey.service" "$SYSTEMD_DEST/hermeskey.service"
install -m 0644 "$ROOT/systemd/user/hermeskey-ydotoold.service" "$SYSTEMD_DEST/hermeskey-ydotoold.service"
install -m 0644 "$ROOT/config/hermeskey.env.example" "$CONFIG_EXAMPLE_DEST"
install -m 0644 "$ROOT/VERSION" "$VERSION_DEST"
install -m 0644 "$ROOT/desktop/hermeskey.metainfo.xml" "$METADATA_DEST/hermeskey.metainfo.xml"
install -m 0644 "$ROOT/assets/hermeskey-icon.svg" "$ICON_DEST/hermeskey.svg"
# Let icon lookups notice the new icon (directory mtime, and GTK's cache if one exists).
touch "$ICON_THEME_DIR"
if [[ -f "$ICON_THEME_DIR/icon-theme.cache" ]] && command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -q -t "$ICON_THEME_DIR" || true
fi
sed "s|@BIN_DEST@|$BIN_DEST|g" "$ROOT/desktop/hermeskey-status.desktop.in" > "$APPLICATIONS_DEST/hermeskey-status.desktop"
sed "s|@BIN_DEST@|$BIN_DEST|g" "$ROOT/desktop/hermeskey-doctor.desktop.in" > "$APPLICATIONS_DEST/hermeskey-doctor.desktop"
sed "s|@BIN_DEST@|$BIN_DEST|g" "$ROOT/desktop/hermeskey-config.desktop.in" > "$APPLICATIONS_DEST/hermeskey-config.desktop"
sed "s|@BIN_DEST@|$BIN_DEST|g" "$ROOT/desktop/hermeskey-logs.desktop.in" > "$APPLICATIONS_DEST/hermeskey-logs.desktop"
sed "s|@BIN_DEST@|$BIN_DEST|g" "$ROOT/desktop/hermeskey-control-center.desktop.in" > "$APPLICATIONS_DEST/hermeskey-control-center.desktop"
sed "s|@BIN_DEST@|$BIN_DEST|g" "$ROOT/desktop/hermeskey-settings.desktop.in" > "$APPLICATIONS_DEST/hermeskey-settings.desktop"

if [[ ! -f "$CONFIG_DEST" ]]; then
  install -m 0644 "$ROOT/config/hermeskey.env.example" "$CONFIG_DEST"
fi

# Record a non-default venv location so the service, doctor, and hotkey
# script use it (they default to ~/venvs/stt).
if [[ -n "${HERMESKEY_VENV:-}" && "${HERMESKEY_VENV%/}" != "$HOME/venvs/stt" ]] \
  && ! grep -q '^PYTHON_STT=' "$CONFIG_DEST"; then
  printf '\n# Python used for the speech server (set by the installer)\nPYTHON_STT="%s/bin/python"\n' "${HERMESKEY_VENV%/}" >> "$CONFIG_DEST"
  printf 'Recorded custom venv in %s\n' "$CONFIG_DEST"
fi

ln -sfn "$BIN_DEST/hermeskey" "$BIN_DEST/ptt_stt_toggle.sh"
ln -sfn "$BIN_DEST/hermeskey-server.py" "$BIN_DEST/ptt_stt_server.py"
ln -sfn "$BIN_DEST/hermeskey-overlay.py" "$BIN_DEST/ptt_stt_overlay.py"

if systemctl --user list-unit-files | grep -q '^ptt-stt.service'; then
  systemctl --user disable --now ptt-stt.service >/dev/null 2>&1 || true
fi
if systemctl --user list-unit-files | grep -q '^ydotoold.service'; then
  systemctl --user disable --now ydotoold.service >/dev/null 2>&1 || true
fi

# Older versions kept audio and logs world-readable in /tmp. Remove our own
# leftovers (the sticky bit on /tmp prevents touching other users' files).
rm -f /tmp/hermeskey_audio.wav /tmp/hermeskey.log /tmp/hermeskey-server.log /tmp/hermeskey-overlay.log 2>/dev/null || true

systemctl --user daemon-reload
systemctl --user enable hermeskey-ydotoold.service hermeskey.service
# restart (not just start): on upgrades the old server code would otherwise
# keep running until the next login.
systemctl --user restart hermeskey-ydotoold.service
systemctl --user restart hermeskey.service

echo
printf 'HermesKey %s installed.\n\n' "$VERSION"
printf 'Main command: %s\n' "$BIN_DEST/hermeskey"
printf 'Doctor tool:   %s\n' "$BIN_DEST/hermeskey-doctor"
printf 'Config file:   %s\n' "$CONFIG_DEST"
printf 'Version file:  %s\n' "$VERSION_DEST"
printf 'Hotkey target: %s\n' "$BIN_DEST/hermeskey"
printf 'Launchers:     %s\n' "$APPLICATIONS_DEST"
printf 'Control app:   %s\n' "$BIN_DEST/hermeskey-control-center"
printf 'Settings UI:   %s (preview)\n\n' "$BIN_DEST/hermeskey-settings.py"

if [[ "${HERMESKEY_INSTALL_CONTEXT:-}" != "bootstrap" ]]; then
  printf 'Suggested next steps:\n'
printf '  1. Edit %s\n' "$CONFIG_DEST"
printf '  2. Bind your desktop hotkey to: %s\n' "$BIN_DEST/hermeskey"
printf '  3. Restart after config changes: systemctl --user restart hermeskey.service\n'
printf '  4. Read docs: %s\n' 'https://github.com/graygarbage/HermesKey/blob/main/docs/INSTALL.md'
fi
