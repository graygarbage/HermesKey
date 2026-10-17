#!/usr/bin/env bash
# No desktop, model download, or services are needed to validate settings.
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")/.."
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
export HERMESKEY_CONFIG="$tmp/hermeskey.env"
cp config/hermeskey.env.example "$HERMESKEY_CONFIG"

bash bin/hermeskey-doctor --config-only >"$tmp/output"
grep -q 'MODEL preset supported' "$tmp/output"

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
for expected in 'Invalid STT_LANG' 'INSERT_MODE is invalid' 'TYPE_BACKEND is invalid' \
  'COPY_TO_CLIPBOARD is invalid' 'TYPE_KEY_HOLD is invalid' 'TONE_VOLUME is invalid'; do
  grep -q "$expected" "$tmp/output"
done

# A full report must not copy service journal, custom model/venv paths, network
# source names, or literal config values into output intended for support.
secret=PRIVATE_SYNTHETIC_DOCTOR_MARKER
printf 'MODEL=/tmp/%s/model\nPYTHON_STT=/tmp/%s/python\nSTT_LANG=en\nRECORD_SOURCE=alsa_input.%s\n' \
  "$secret" "$secret" "$secret" >"$tmp/private.env"
mkdir -p "$tmp/bin"
cat >"$tmp/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
if [[ "$*" == *status* ]]; then echo PRIVATE_SYNTHETIC_DOCTOR_MARKER; fi
exit 1
EOF
cat >"$tmp/bin/pactl" <<'EOF'
#!/usr/bin/env bash
printf '1\talsa_input.PRIVATE_SYNTHETIC_DOCTOR_MARKER\tPipeWire\n'
EOF
chmod +x "$tmp/bin/systemctl" "$tmp/bin/pactl"
HERMESKEY_CONFIG="$tmp/private.env" XDG_RUNTIME_DIR="$tmp/$secret-runtime" \
  PATH="$tmp/bin:$PATH" bash bin/hermeskey-doctor >"$tmp/private-report"
if grep -Eq "$secret|HTTP Request:|Service snippets|include this output plus" "$tmp/private-report"; then
  echo 'Doctor included private diagnostic data' >&2
  exit 1
fi
grep -q 'Configured RECORD_SOURCE found' "$tmp/private-report"
grep -q 'Review this report before sharing' "$tmp/private-report"
printf 'Doctor config validation and privacy checks passed.\n'
