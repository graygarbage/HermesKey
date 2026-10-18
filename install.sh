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
# The user services use %h/.config and do not inherit XDG_CONFIG_HOME.
# Keep one canonical config for all installed entry points.
CONFIG_DEST_DIR="$HOME/.config/$APP_ID"
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

# A running recording must be stopped by the user before files/services change.
# Do not toggle it here: stopping automatically could copy private text.
if [[ -f "${XDG_RUNTIME_DIR:-/run/user/$UID}/hermeskey_recording.pid" ]]; then
  printf 'Finish dictation before installing; a recording is in progress.\n' >&2
  exit 1
fi

# Do not follow links to a different config directory/file during comparison
# or installation, even if the link points to another private file.
if [[ -L "$CONFIG_DEST_DIR" || -L "$CONFIG_DEST" ]]; then
  printf 'Refusing symlinked HermesKey config path; inspect it privately.\n' >&2
  exit 1
fi

# Upgrade an older custom-XDG installation only if there is no conflicting
# canonical file. Read/copy bytes only; never source a legacy config here.
LEGACY_CONFIG=""
LEGACY_ARCHIVE=""
if [[ -n "${XDG_CONFIG_HOME:-}" ]]; then
  [[ "$XDG_CONFIG_HOME" == /* ]] || { printf 'XDG_CONFIG_HOME must be absolute.\n' >&2; exit 1; }
  candidate="${XDG_CONFIG_HOME%/}/$APP_ID/hermeskey.env"
  if [[ "$candidate" != "$CONFIG_DEST" && ! "$candidate" -ef "$CONFIG_DEST" ]]; then
    if [[ -L "$XDG_CONFIG_HOME" || -L "${candidate%/*}" || -L "$candidate" ]]; then
      printf 'Refusing symlinked legacy HermesKey config; inspect it manually.\n' >&2
      exit 1
    fi
    if [[ -e "$candidate" ]]; then
      [[ -f "$candidate" ]] || { printf 'Invalid legacy HermesKey config.\n' >&2; exit 1; }
      LEGACY_CONFIG="$candidate"
      LEGACY_ARCHIVE="$candidate.pre-hermeskey-xdg-migration"
      if [[ -e "$LEGACY_ARCHIVE" || -L "$LEGACY_ARCHIVE" ]]; then
        printf 'Legacy HermesKey migration backup already exists; inspect both configs before upgrading.\n' >&2
        exit 1
      fi
      if [[ -e "$CONFIG_DEST" ]] && ! cmp -s -- "$CONFIG_DEST" "$LEGACY_CONFIG"; then
        printf 'Conflicting canonical and custom-XDG HermesKey configs; choose one before upgrading. Neither was modified.\n' >&2
        exit 1
      fi
    fi
  fi
fi

# Private from creation, even on first install with a permissive umask.
mkdir -p "$CONFIG_DEST_DIR"
[[ -d "$CONFIG_DEST_DIR" && ! -L "$CONFIG_DEST_DIR" ]] || { printf 'Invalid HermesKey config directory.\n' >&2; exit 1; }
chmod 0700 "$CONFIG_DEST_DIR"
if [[ -n "$LEGACY_CONFIG" ]]; then
  if [[ ! -e "$CONFIG_DEST" ]]; then
    install -m 0600 -- "$LEGACY_CONFIG" "$CONFIG_DEST"
  fi
  # Archive the old path so subsequent GUI edits and upgrades cannot disagree
  # with a stale custom-XDG file. Do not discard its contents or expose a
  # previously world-readable legacy config through its backup.
  chmod 0600 "$LEGACY_CONFIG"
  mv -- "$LEGACY_CONFIG" "$LEGACY_ARCHIVE"
  printf 'Migrated custom-XDG HermesKey config to the service path; private legacy backup retained.\n'
fi
if [[ -e "$CONFIG_DEST" ]]; then
  [[ -f "$CONFIG_DEST" ]] || { printf 'Invalid HermesKey config file.\n' >&2; exit 1; }
  chmod 0600 "$CONFIG_DEST"
fi
mkdir -p "$BIN_DEST" "$SYSTEMD_DEST" "$APPLICATIONS_DEST" "$METADATA_DEST" "$DATA_DEST_DIR" "$ICON_DEST"

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
install -m 0644 "$ROOT/bin/hermeskey_settings_config.py" "$BIN_DEST/hermeskey_settings_config.py"
install -m 0644 "$ROOT/bin/hermeskey_audio_sources.py" "$BIN_DEST/hermeskey_audio_sources.py"
install -m 0644 "$ROOT/bin/hermeskey_system_panel.py" "$BIN_DEST/hermeskey_system_panel.py"
install -m 0755 "$ROOT/bin/hermeskey_system_tools.py" "$BIN_DEST/hermeskey_system_tools.py"
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
  install -m 0600 "$ROOT/config/hermeskey.env.example" "$CONFIG_DEST"
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
printf 'Settings UI:   %s\n' "$BIN_DEST/hermeskey-settings.py"
printf 'App launcher:  %s\n\n' "$APPLICATIONS_DEST/hermeskey-settings.desktop"

if [[ "${HERMESKEY_INSTALL_CONTEXT:-}" != "bootstrap" ]]; then
  printf 'Suggested next steps:\n'
printf '  1. Edit %s\n' "$CONFIG_DEST"
printf '  2. Bind your desktop hotkey to: %s\n' "$BIN_DEST/hermeskey"
printf '  3. Restart after config changes: systemctl --user restart hermeskey.service\n'
printf '  4. Read docs: %s\n' 'https://github.com/graygarbage/HermesKey/blob/main/docs/INSTALL.md'
fi
