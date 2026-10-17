#!/usr/bin/env bash
set -euo pipefail

BIN_DEST="$HOME/.local/bin"
SYSTEMD_DEST="$HOME/.config/systemd/user"
SHARE_DEST_DIR="${XDG_DATA_HOME:-$HOME/.local/share}"
APPLICATIONS_DEST="$SHARE_DEST_DIR/applications"
METADATA_DEST="$SHARE_DEST_DIR/metainfo"
DATA_DEST_DIR="$SHARE_DEST_DIR/hermeskey"
ICON_DEST="$SHARE_DEST_DIR/icons/hicolor/scalable/apps"

systemctl --user disable --now hermeskey.service >/dev/null 2>&1 || true
systemctl --user disable --now hermeskey-ydotoold.service >/dev/null 2>&1 || true

rm -f \
  "$BIN_DEST/hermeskey" \
  "$BIN_DEST/hermeskey-server.py" \
  "$BIN_DEST/hermeskey-overlay.py" \
  "$BIN_DEST/hermeskey-doctor" \
  "$BIN_DEST/hermeskey-desktop-status" \
  "$BIN_DEST/hermeskey-desktop-doctor" \
  "$BIN_DEST/hermeskey-open-config" \
  "$BIN_DEST/hermeskey-open-logs" \
  "$BIN_DEST/hermeskey-restart-services" \
  "$BIN_DEST/hermeskey-control-center" \
  "$BIN_DEST/hermeskey-settings.py" \
  "$BIN_DEST/hermeskey_settings_config.py" \
  "$BIN_DEST/hermeskey_audio_sources.py" \
  "$BIN_DEST/hermeskey_system_panel.py" \
  "$BIN_DEST/hermeskey_system_tools.py" \
  "$BIN_DEST/ptt_stt_toggle.sh" \
  "$BIN_DEST/ptt_stt_server.py" \
  "$BIN_DEST/ptt_stt_overlay.py" \
  "$SYSTEMD_DEST/hermeskey.service" \
  "$SYSTEMD_DEST/hermeskey-ydotoold.service" \
  "$APPLICATIONS_DEST/hermeskey-status.desktop" \
  "$APPLICATIONS_DEST/hermeskey-doctor.desktop" \
  "$APPLICATIONS_DEST/hermeskey-config.desktop" \
  "$APPLICATIONS_DEST/hermeskey-logs.desktop" \
  "$APPLICATIONS_DEST/hermeskey-control-center.desktop" \
  "$APPLICATIONS_DEST/hermeskey-settings.desktop" \
  "$METADATA_DEST/hermeskey.metainfo.xml" \
  "$DATA_DEST_DIR/VERSION" \
  "$ICON_DEST/hermeskey.svg"

systemctl --user daemon-reload

echo "HermesKey uninstalled. Config files in ~/.config/hermeskey were left untouched."
