#!/usr/bin/env bash
# Required system dependencies for the supported Wayland install path.
set -euo pipefail

missing=()
for cmd in ffmpeg wl-copy notify-send ydotool ydotoold pactl systemctl; do
  command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
done
if (( ${#missing[@]} )); then
  printf 'Missing system commands: %s\n' "${missing[*]}" >&2
fi

if ! python3 -c 'import PySide6.QtWidgets' >/dev/null 2>&1; then
  printf 'Missing system Python PySide6.QtWidgets (the default overlay needs it).\n' >&2
  missing+=(PySide6)
fi
if ! systemctl --user show-environment >/dev/null 2>&1; then
  printf 'Cannot reach the systemd user manager. Install from a logged-in desktop session, without sudo.\n' >&2
  missing+=(user-systemd)
fi
if [[ ! -c /dev/uinput || ! -r /dev/uinput || ! -w /dev/uinput ]]; then
  printf 'Cannot access /dev/uinput. Check your active graphical seat and udev/logind uaccess rules. Do not chmod 666 or run ydotoold as root.\n' >&2
  missing+=(uinput)
fi

if (( ${#missing[@]} )); then
  printf 'Install the distro packages listed at https://github.com/graygarbage/HermesKey/blob/main/docs/INSTALL.md and retry. No HermesKey files were installed.\n' >&2
  exit 1
fi
printf 'Preflight passed: system tools, overlay, user manager, and /dev/uinput are available.\n'
