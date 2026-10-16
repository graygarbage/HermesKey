#!/usr/bin/env bash
# Exercise concurrent hotkey invocations without a real microphone or speech model.
set -euo pipefail

cd "$(dirname -- "${BASH_SOURCE[0]}")/.."
ROOT="$PWD"
TMP="$(mktemp -d)"
cleanup() {
  if [[ -f "$TMP/runtime/hermeskey_recording.pid" ]]; then
    kill "$(<"$TMP/runtime/hermeskey_recording.pid")" 2>/dev/null || true
  fi
  rm -rf "$TMP"
}
trap cleanup EXIT
mkdir -p "$TMP/bin" "$TMP/runtime" "$TMP/state" "$TMP/config"

printf '%s\n' 'OVERLAY_ENABLED=0' 'SOUND_ENABLED=0' 'INSERT_MODE=clipboard' \
  'COPY_TO_CLIPBOARD=1' 'CLIP_CMD=wl-copy' >"$TMP/config/hermeskey.env"

# The first ping holds the start transition long enough for another hotkey.
# Subsequent pings return immediately.
cat >"$TMP/bin/nc" <<'EOF'
#!/usr/bin/env bash
if [[ ! -f "$TEST_TMP/ping-done" ]]; then
  touch "$TEST_TMP/ping-done" "$TEST_TMP/starting"
  sleep 1
fi
exit 0
EOF
cat >"$TMP/bin/ffmpeg" <<'EOF'
#!/usr/bin/env bash
printf 'start\n' >>"$TEST_TMP/recordings"
printf 'fake wav' >"${*: -1}"
trap 'exit 0' TERM
while :; do sleep 0.1 & wait "$!" || :; done
EOF
cat >"$TMP/bin/python3" <<'EOF'
#!/usr/bin/env bash
if [[ "${1:-}" == '-' ]]; then
  touch "$TEST_TMP/transcribing"
  sleep 1
  printf '{"status":"ok","text":"first transcript"}\n'
else
  exec /usr/bin/python3 "$@"
fi
EOF
cat >"$TMP/bin/wl-copy" <<'EOF'
#!/usr/bin/env bash
tee "$TEST_TMP/clipboard" >/dev/null
EOF
cat >"$TMP/bin/notify-send" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
chmod +x "$TMP/bin/"*
export TEST_TMP="$TMP" PATH="$TMP/bin:$PATH" XDG_RUNTIME_DIR="$TMP/runtime" \
  XDG_STATE_HOME="$TMP/state" HERMESKEY_CONFIG="$TMP/config/hermeskey.env"

wait_for() {
  local file="$1"
  for _ in {1..100}; do
    [[ -e "$file" ]] && return 0
    sleep 0.05
  done
  printf 'Timed out waiting for %s\n' "$file" >&2
  exit 1
}

"$ROOT/bin/hermeskey" >"$TMP/start-output" &
start_pid=$!
wait_for "$TMP/starting"
"$ROOT/bin/hermeskey" >"$TMP/busy-start-output"
wait "$start_pid"
[[ -f "$TMP/runtime/hermeskey_recording.pid" ]]
[[ "$(wc -l <"$TMP/recordings")" == 1 ]]

"$ROOT/bin/hermeskey" >"$TMP/stop-output" &
stop_pid=$!
wait_for "$TMP/transcribing"
"$ROOT/bin/hermeskey" >"$TMP/busy-transcribe-output"
wait "$stop_pid"
[[ "$(<"$TMP/clipboard")" == 'first transcript' ]]
[[ "$(wc -l <"$TMP/recordings")" == 1 ]]
[[ ! -e "$TMP/runtime/hermeskey_recording.pid" ]]

# The long-lived ffmpeg child must not retain the lock after a start.
"$ROOT/bin/hermeskey" >"$TMP/second-start-output"
[[ -f "$TMP/runtime/hermeskey_recording.pid" ]]
[[ "$(wc -l <"$TMP/recordings")" == 2 ]]
printf 'Toggle locking test passed.\n'
