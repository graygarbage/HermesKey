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
  [[ "$CHANNEL" != "release" ]] || need_cmd sha256sum
fi

latest_release_tag() {
  local json
  json="$(curl -fsSL --proto '=https' --proto-redir '=https' "$API_URL")"

  RELEASE_JSON="$json" python3 - <<'PY'
import json
import os
import re

payload = json.loads(os.environ['RELEASE_JSON'])
tag = payload.get('tag_name', '')
if not isinstance(tag, str) or not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+', tag):
    raise SystemExit(1)
name = f"hermeskey-{tag[1:]}.tar.gz"
if sum(asset.get('name') == name for asset in payload.get('assets', [])) != 1:
    raise SystemExit(1)
print(tag)
PY
}

# Reviewed digests live in the bootstrap code, NOT the release API response or
# another file downloaded next to the archive. Updating this allowlist requires
# an independent PR after each release asset has been built and inspected.
trusted_release_digest() {
  case "$1" in
    v0.6.3) printf '%s\n' '167bd4336d875af01b115869cb1b8e85baa35fb316d6364f728b7138d499929a' ;;
    v0.6.4) printf '%s\n' '6f046010a3ce0afd58535739d4bc560bc42cd0dac3d5a2eba58caac412219900' ;;
    *) return 1 ;;
  esac
}

resolve_release() {
  local tag
  tag="$(latest_release_tag)" || fail "Could not resolve the latest release archive; refusing to install from main. Retry later, or explicitly pass --main if you want untagged code."
  EXPECTED_DIGEST="$(trusted_release_digest "$tag")" || fail "Latest release has no reviewed digest; refusing to install it. Wait for a reviewed bootstrap update."
  ARCHIVE_URL="https://github.com/$REPO/releases/download/$tag/hermeskey-${tag#v}.tar.gz"
}

# v0.6.3 predates the reviewed lock. Its archive is still the current public
# release, so a newer trusted bootstrap must override its broad ranges instead
# of silently resolving them. The exact pins are mirrored in requirements.txt
# and tested for equality; remove this compatibility block after that release
# is no longer offered by the default channel.
reviewed_legacy_requirements() {
  cat <<'PINS'
faster-whisper==1.2.1
av==18.0.0
ctranslate2==4.8.1
huggingface-hub==1.27.0
tokenizers==0.23.1
onnxruntime==1.28.0
numpy==2.5.2
PyYAML==6.0.3
setuptools==84.0.0
tqdm==4.70.0
anyio==4.14.2
certifi==2026.7.22
click==8.4.2
filelock==3.32.2
flatbuffers==25.12.19
fsspec==2026.7.0
h11==0.16.0
hf-xet==1.6.0
httpcore==1.0.9
httpx==0.28.1
idna==3.18
packaging==26.3
protobuf==7.35.1
typing-extensions==4.16.0
PINS
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

  # No unreviewed pip/wheel upgrade or source build during installation.
  local requirements="$ROOT/requirements.txt"
  if [[ "$LOCAL_SOURCE" == 0 && "$CHANNEL" == "release" && "$(tr -d '[:space:]' <"$ROOT/VERSION")" == "0.6.3" ]]; then
    requirements="$TMP_DIR/reviewed-speech-requirements.txt"
    reviewed_legacy_requirements >"$requirements"
  fi
  "$VENV_DIR/bin/python" -m pip install --only-binary=:all: --no-input --disable-pip-version-check -r "$requirements"
  "$VENV_DIR/bin/python" -m pip check || fail "Speech dependencies conflict; inspect the venv privately before restarting services."
  ok "Pinned Python dependencies installed"
}

banner

# Dependency updates and service restarts must not interrupt an active
# dictation. Never stop it automatically (that could insert or copy text).
if [[ -f "${XDG_RUNTIME_DIR:-/run/user/$UID}/hermeskey_recording.pid" ]]; then
  fail "Finish dictation before upgrading; recording is active."
fi

if [[ "$LOCAL_SOURCE" == 1 ]]; then
  ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
  step "Using checkout at $ROOT"
else
  TMP_DIR="$(mktemp -d)"
  trap 'rm -rf "$TMP_DIR"' EXIT

  if [[ "$CHANNEL" == "main" ]]; then
    ARCHIVE_URL="$MAIN_TARBALL_URL"
  else
    resolve_release
  fi
  ARCHIVE_PATH="$TMP_DIR/hermeskey.tar.gz"
  EXTRACT_DIR="$TMP_DIR/extract"

  step "Downloading HermesKey"
  say "Source: $ARCHIVE_URL"
  curl -fsSL --proto '=https' --proto-redir '=https' "$ARCHIVE_URL" -o "$ARCHIVE_PATH"
  if [[ "$CHANNEL" == "release" ]]; then
    actual_digest="$(sha256sum "$ARCHIVE_PATH")"
    actual_digest="${actual_digest%% *}"
    [[ "$actual_digest" == "$EXPECTED_DIGEST" ]] || fail "Release archive digest mismatch; refusing to extract or execute it."
    ok "Release archive matches reviewed digest"
  else
    warn "Explicit --main selected: mutable archive has no pinned release digest."
  fi
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
  --socket "${HERMESKEY_SMOKE_SOCKET:-${XDG_RUNTIME_DIR:-/run/user/$UID}/hermeskey.sock}" \
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
