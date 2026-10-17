#!/usr/bin/env bash
# End-to-end toggle tests with a fake recorder/server/typing backend. No desktop input.
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")/.."
ROOT="$PWD"
TMP="$(mktemp -d)"
cleanup() {
  if [[ -f "$TMP/runtime/hermeskey_recording.pid" ]]; then
    kill "$(<"$TMP/runtime/hermeskey_recording.pid")" 2>/dev/null || true
  fi
  if [[ -n "${socket_pid:-}" ]]; then
    kill "$socket_pid" 2>/dev/null || true
  fi
  rm -rf "$TMP"
}
trap cleanup EXIT
mkdir -p "$TMP/bin" "$TMP/runtime" "$TMP/state" "$TMP/config"

cat >"$TMP/bin/ffmpeg" <<'EOF'
#!/usr/bin/env bash
printf 'fake audio' >"${*: -1}"
trap 'exit 0' TERM
while :; do sleep 0.1 & wait "$!" || :; done
EOF
cat >"$TMP/bin/nc" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
cat >"$TMP/bin/python3" <<'EOF'
#!/usr/bin/env bash
if [[ "${1:-}" == '-' && -n "${REQUEST_WAV:-}" ]]; then
  TEST_TEXT="$TEST_TEXT" exec /usr/bin/python3 -c 'import json,os; print(json.dumps({"status":"ok","text":os.environ["TEST_TEXT"]}))'
else
  exec /usr/bin/python3 "$@"
fi
EOF
cat >"$TMP/bin/ydotool" <<'EOF'
#!/usr/bin/env bash
if [[ "${1:-}" == type && "${2:-}" == --help ]]; then
  echo '--key-hold'; exit 0
fi
printf '%s\n' "$1" >>"$TEST_TMP/events"
[[ "$1" != key || "${TEST_FAIL_KEY:-0}" != 1 ]] || exit 4
[[ "$1" != type || "${TEST_FAIL_TYPE:-0}" != 1 ]] || exit 4
EOF
cat >"$TMP/bin/wl-copy" <<'EOF'
#!/usr/bin/env bash
[[ "${TEST_FAIL_CLIP:-0}" != 1 ]] || exit 1
tee "$TEST_TMP/clipboard" >/dev/null
EOF
cat >"$TMP/bin/notify-send" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"$TEST_TMP/notifications"
EOF
cat >"$TMP/bin/kdotool" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "${TEST_UUID:-11111111-1111-1111-1111-111111111111}"
EOF
cat >"$TMP/bin/qdbus" <<'EOF'
#!/usr/bin/env bash
[[ "${TEST_UNKNOWN:-0}" != 1 ]] || exit 0
printf '%s\n' "uuid: ${TEST_UUID:-11111111-1111-1111-1111-111111111111}" \
  'desktopFile: org.kde.konsole' 'resourceClass: konsole' 'caption: test window'
EOF
chmod +x "$TMP/bin/"*
export TEST_TMP="$TMP" PATH="$TMP/bin:$PATH" XDG_RUNTIME_DIR="$TMP/runtime" \
  XDG_STATE_HOME="$TMP/state" HERMESKEY_CONFIG="$TMP/config/hermeskey.env"
/usr/bin/python3 - "$TMP/runtime/typing.sock" <<'PY' &
import socket,sys,time
s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
s.bind(sys.argv[1]);s.listen(1);time.sleep(90)
PY
socket_pid=$!
for _ in {1..30}; do [[ -S "$TMP/runtime/typing.sock" ]] && break; sleep 0.05; done
[[ -S "$TMP/runtime/typing.sock" ]]

run_case() {
  local text="$1" copy="$2" shortcut="$3"
  export TEST_TEXT="$text"
  printf '%s\n' 'OVERLAY_ENABLED=0' 'SOUND_ENABLED=0' 'INSERT_MODE=type' \
    "FOCUS_SAFE_MODE=${TEST_FOCUS_SAFE:-0}" "COPY_TO_CLIPBOARD=$copy" 'TYPE_BACKEND=ydotool' "YDOTOOL_SOCKET_PATH=$TMP/runtime/typing.sock" \
    "PASTE_SHORTCUT=$shortcut" >"$HERMESKEY_CONFIG"
  rm -f "$TMP/clipboard" "$TMP/events" "$TMP/notifications"
  "$ROOT/bin/hermeskey" >/dev/null
  if [[ "${TEST_SWITCH_FOCUS:-0}" == 1 ]]; then
    TEST_UUID=22222222-2222-2222-2222-222222222222; export TEST_UUID
  fi
  "$ROOT/bin/hermeskey" >"$TMP/result"
  unset TEST_UUID
}

run_case '你好，世界！' 1 auto
[[ "$(<"$TMP/clipboard")" == '你好，世界！' ]]
[[ "$(<"$TMP/events")" == key ]]
grep -q 'Paste shortcut sent' "$TMP/result"

run_case 'Français été' 1 ctrl-v
[[ "$(<"$TMP/clipboard")" == 'Français été' ]]
[[ "$(<"$TMP/events")" == key ]]

TEST_FAIL_KEY=1; export TEST_FAIL_KEY
run_case 'العربية' 1 ctrl-v
[[ "$(<"$TMP/clipboard")" == 'العربية' ]]
grep -q 'paste shortcut failed' "$TMP/result"
unset TEST_FAIL_KEY

TEST_UNKNOWN=1; export TEST_UNKNOWN
run_case '日本語' 1 auto
[[ "$(<"$TMP/clipboard")" == '日本語' && ! -e "$TMP/events" ]]
grep -q 'paste target unknown' "$TMP/result"
unset TEST_UNKNOWN

TEST_FAIL_CLIP=1; export TEST_FAIL_CLIP
run_case 'ไทย' 1 auto
[[ ! -e "$TMP/clipboard" && ! -e "$TMP/events" ]]
grep -q 'not inserted or copied' "$TMP/result"
unset TEST_FAIL_CLIP

run_case 'Привет мир' 0 auto
[[ ! -e "$TMP/clipboard" && ! -e "$TMP/events" ]]
grep -q 'not inserted or copied' "$TMP/result"
grep -q 'clipboard backup' "$TMP/notifications"

run_case 'hello123' 0 auto
[[ ! -e "$TMP/clipboard" ]]
[[ "$(<"$TMP/events")" == type ]]

TEST_FAIL_TYPE=1; export TEST_FAIL_TYPE
run_case 'hello123' 0 auto
[[ ! -e "$TMP/clipboard" ]]
grep -q 'Not inserted or copied' "$TMP/result"
unset TEST_FAIL_TYPE

TEST_FOCUS_SAFE=1 TEST_SWITCH_FOCUS=1; export TEST_FOCUS_SAFE TEST_SWITCH_FOCUS
run_case 'hello123' 0 auto
[[ ! -e "$TMP/clipboard" && ! -e "$TMP/events" ]]
grep -q 'focus changed' "$TMP/result"
unset TEST_FOCUS_SAFE TEST_SWITCH_FOCUS

if grep -qE '你好|Français|Привет|العربية|日本語|ไทย|hello123' "$TMP/state/hermeskey/hermeskey.log"; then
  echo 'Private transcript leaked to the log' >&2
  exit 1
fi
printf 'Unicode insertion policy tests passed.\n'
