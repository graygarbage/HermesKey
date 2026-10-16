#!/usr/bin/env bash
# Fail early if preserved configuration points the speech service at a missing venv.
set -euo pipefail

venv_dir="$1"
config_file="${XDG_CONFIG_HOME:-$HOME/.config}/hermeskey/hermeskey.env"
python_stt="$venv_dir/bin/python"
if [[ -f "$config_file" ]]; then
  # HermesKey's hotkey also sources this user-owned configuration as shell.
  # Do it in a subshell so config variables do not alter bootstrap itself.
  python_stt="$(
    # shellcheck disable=SC1090
    source "$config_file" >/dev/null
    printf '%s' "${PYTHON_STT:-$venv_dir/bin/python}"
  )"
fi

if [[ ! -x "$python_stt" ]]; then
  printf 'Configured speech Python does not exist: %s\n' "$python_stt" >&2
  printf 'Check PYTHON_STT in %s. The installer preserves existing configuration.\n' "$config_file" >&2
  printf 'For a fresh install, back up and remove that config file, then rerun bootstrap.\n' >&2
  exit 1
fi
if ! "$python_stt" -c 'import faster_whisper' >/dev/null 2>&1; then
  printf 'Configured speech Python cannot import faster_whisper: %s\n' "$python_stt" >&2
  printf 'Check PYTHON_STT in %s and install requirements into that venv.\n' "$config_file" >&2
  exit 1
fi
printf 'Speech Python ready: %s\n' "$python_stt"
