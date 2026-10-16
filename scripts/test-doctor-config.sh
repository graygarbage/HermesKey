#!/usr/bin/env bash
# No desktop, model download, or services are needed to validate settings.
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")/.."
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
export HERMESKEY_CONFIG="$tmp/hermeskey.env"
cp config/hermeskey.env.example "$HERMESKEY_CONFIG"

bash bin/hermeskey-doctor --config-only >"$tmp/output"
grep -q 'MODEL=medium' "$tmp/output"

printf '\nMODEL=invalid-model-name\nSTT_LANG=\n' >>"$HERMESKEY_CONFIG"
bash bin/hermeskey-doctor --config-only >"$tmp/output"
grep -q 'Unknown faster-whisper model alias' "$tmp/output"
grep -q 'automatic detection' "$tmp/output"

printf '\nMODEL=org/custom-model\nSTT_LANG=haw\n' >>"$HERMESKEY_CONFIG"
bash bin/hermeskey-doctor --config-only >"$tmp/output"
grep -q 'custom path or Hugging Face ID' "$tmp/output"

printf '\nSTT_LANG=xyz\nINSERT_MODE=broken\nTYPE_BACKEND=broken\nCOPY_TO_CLIPBOARD=maybe\nTYPE_KEY_HOLD=fast\nTONE_VOLUME=loud\n' >>"$HERMESKEY_CONFIG"
if bash bin/hermeskey-doctor --config-only >"$tmp/output"; then
  echo 'Expected invalid configuration to fail' >&2
  exit 1
fi
for expected in 'Invalid STT_LANG=xyz' 'INSERT_MODE=broken' 'TYPE_BACKEND=broken' \
  'COPY_TO_CLIPBOARD=maybe' 'TYPE_KEY_HOLD=fast' 'TONE_VOLUME=loud'; do
  grep -q "$expected" "$tmp/output"
done
printf 'Doctor config validation passed.\n'
