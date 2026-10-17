#!/usr/bin/env bash
set -euo pipefail

REPO="graygarbage/HermesKey"
API_URL="https://api.github.com/repos/$REPO/releases/latest"
MAIN_TARBALL_URL="https://github.com/$REPO/archive/refs/heads/main.tar.gz"
CHANNEL="release"
LOCAL_SOURCE=0
VENV_DIR="${HERMESKEY_VENV:-$HOME/venvs/stt}"
SKIP_VENV="${HERMESKEY_SKIP_VENV:-0}"

if [[ -t 1 ]]; then
  BOLD='\033[1m'
  BLUE='\033[34m'
  GREEN='\033[32m'
  YELLOW='\033[33m'
  RED='\033[31m'
  RESET='\033[0m'
else
  BOLD=''
  BLUE=''
  GREEN=''
  YELLOW=''
  RED=''
  RESET=''
fi

say() { printf '%b\n' "$*"; }
step() { say "${BLUE}${BOLD}==>${RESET} $*"; }
ok() { say "${GREEN}${BOLD}✔${RESET} $*"; }
warn() { say "${YELLOW}${BOLD}!${RESET} $*"; }
fail() { say "${RED}${BOLD}✘${RESET} $*" >&2; exit 1; }

banner() {
  say "${BOLD}HermesKey bootstrap installer${RESET}"
  say "Local-first push-to-talk speech-to-text for Linux Wayland desktops"
  say
}

usage() {
  cat <<EOF
HermesKey bootstrap installer

Usage:
  bash bootstrap.sh [--main | --local] [--skip-venv]

Options:
  --main       install from the current main branch instead of the latest release
  --local      install from this checkout (for testing a PR)
  --skip-venv  skip Python venv creation and pip install
EOF
}

for arg in "$@"; do
  case "$arg" in
    --main)
      CHANNEL="main"
      ;;
    --local)
      LOCAL_SOURCE=1
      ;;
    --skip-venv)
      SKIP_VENV=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "Unknown argument: $arg"
      ;;
  esac
done

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

need_cmd bash
need_cmd python3
if [[ "$LOCAL_SOURCE" == 0 ]]; then
  need_cmd curl
  need_cmd tar
  need_cmd mktemp
fi

latest_asset_url() {
  local json
  json="$(curl -fsSL "$API_URL")"

  RELEASE_JSON="$json" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ['RELEASE_JSON'])
for asset in payload.get('assets', []):
    url = asset.get('browser_download_url', '')
    if url.endswith('.tar.gz') and 'hermeskey-' in url:
        print(url)
        raise SystemExit(0)
raise SystemExit(1)
PY
}

download_url() {
  if [[ "$CHANNEL" == "main" ]]; then
    printf '%s\n' "$MAIN_TARBALL_URL"
    return 0
  fi

  latest_asset_url || {
    warn "Could not resolve latest release asset, falling back to main branch archive."
    printf '%s\n' "$MAIN_TARBALL_URL"
  }
}

setup_python_env() {
  [[ "$SKIP_VENV" == "1" ]] && {
    warn "Skipping Python environment setup because --skip-venv was requested."
    return 0
  }

  step "Preparing Python environment at $VENV_DIR"

  if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    python3 -m venv "$VENV_DIR" || fail "Failed to create venv at $VENV_DIR. Make sure python3-venv is installed."
    ok "Created venv: $VENV_DIR"
  else
    ok "Using existing venv: $VENV_DIR"
  fi

  "$VENV_DIR/bin/python" -m pip install -U pip wheel >/dev/null
  "$VENV_DIR/bin/pip" install -r "$ROOT/requirements.txt"
  ok "Python dependencies installed"
}

banner

if [[ "$LOCAL_SOURCE" == 1 ]]; then
  ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
  step "Using checkout at $ROOT"
else
  TMP_DIR="$(mktemp -d)"
  trap 'rm -rf "$TMP_DIR"' EXIT

  ARCHIVE_URL="$(download_url)"
  ARCHIVE_PATH="$TMP_DIR/hermeskey.tar.gz"
  EXTRACT_DIR="$TMP_DIR/extract"

  step "Downloading HermesKey"
  say "Source: $ARCHIVE_URL"
  curl -fsSL "$ARCHIVE_URL" -o "$ARCHIVE_PATH"
  mkdir -p "$EXTRACT_DIR"
  tar -xzf "$ARCHIVE_PATH" -C "$EXTRACT_DIR"

  if [[ -f "$EXTRACT_DIR/install.sh" ]]; then
    ROOT="$EXTRACT_DIR"
  else
    ROOT="$(find "$EXTRACT_DIR" -mindepth 1 -maxdepth 1 -type d | head -n1)"
  fi
  [[ -n "${ROOT:-}" && -f "$ROOT/install.sh" ]] || fail "Could not find install.sh in extracted archive."
  ok "Archive extracted"
fi
step "Checking system dependencies and desktop access"
bash "$ROOT/scripts/preflight.sh"
setup_python_env
step "Checking preserved speech configuration"
bash "$ROOT/scripts/check-config.sh" "$VENV_DIR"

step "Running HermesKey installer"
chmod +x "$ROOT/install.sh"
HERMESKEY_INSTALL_CONTEXT=bootstrap HERMESKEY_VENV="$VENV_DIR" bash "$ROOT/install.sh"

step "Waiting for model and verifying transcription"
if ! python3 "$ROOT/scripts/verify-install.py" \
  --socket "${HERMESKEY_SMOKE_SOCKET:-${XDG_RUNTIME_DIR:-/tmp}/hermeskey.sock}" \
  --model-timeout "${HERMESKEY_MODEL_TIMEOUT:-600}" \
  --smoke-timeout "${HERMESKEY_SMOKE_TIMEOUT:-180}"; then
  fail "HermesKey files were installed, but runtime validation failed. See errors above and run hermeskey-doctor."
fi

ok "HermesKey bootstrap complete"
say
say "${BOLD}What you now have${RESET}"
say "  • ~/.local/bin/hermeskey"
say "  • ~/.config/systemd/user/hermeskey.service"
say "  • ~/.config/systemd/user/hermeskey-ydotoold.service"
say "  • ~/.config/hermeskey/hermeskey.env"
say
say "${BOLD}Next steps${RESET}"
say "  1. Open HermesKey Settings from your app menu to choose your microphone and spoken language"
say "  2. Bind your desktop hotkey to: ~/.local/bin/hermeskey"
say "  3. Check runtime health in Settings or with: hermeskey --status"
say "  4. Run diagnostics in Settings or with: hermeskey-doctor"
say "  5. Read the install guide: https://github.com/graygarbage/HermesKey/blob/main/docs/INSTALL.md"
