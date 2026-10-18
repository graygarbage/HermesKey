#!/usr/bin/env bash
# End-to-end toggle tests with a fake recorder/server/typing backend. No desktop input.
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")/.."
ROOT="$PWD"
TMP="$(mktemp -d)"
cleanup() {
  if [[ -f "$TMP/runtime/hermeskey_recording.pid" ]]; then
    state="$(<"$TMP/runtime/hermeskey_recording.pid")"
    kill "${state%%:*}" 2>/dev/null || true
  fi
  if [[ -n "${socket_pid:-}" ]]; then
    kill "$socket_pid" 2>/dev/null || true
  fi
  if [[ -n "${untrusted_pid:-}" ]]; then
    kill "$untrusted_pid" 2>/dev/null || true
  fi
  rm -rf "$TMP"
}
trap cleanup EXIT
mkdir -p "$TMP/bin" "$TMP/runtime" "$TMP/state" "$TMP/config" "$TMP/shared"
chmod 700 "$TMP/runtime"
chmod 777 "$TMP/shared"

cat >"$TMP/bin/ffmpeg" <<'EOF'
#!/usr/bin/env bash
printf 'fake audio' >"${*: -1}"
printf '%s\n' "PRIVATE_SYNTHETIC_RECORDER_ERROR ${TEST_SOURCE:-}" >&2
trap 'exit 0' TERM
while :; do sleep 0.1 & wait "$!" || :; done
EOF
cat >"$TMP/bin/nc" <<'EOF'
#!/usr/bin/env bash
[[ "${TEST_REQUIRE_SERVER_READY:-0}" != 1 || -e "$TEST_TMP/server-ready" ]]
EOF
cat >"$TMP/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
exit 1
EOF
cat >"$TMP/bin/python3" <<'EOF'
#!/usr/bin/env bash
if [[ "${1:-}" == "$TEST_TMP/hermeskey-server-fake.py" ]]; then
  printf '%s\n' "$SOCK $MODEL $STT_LANG" >"$TEST_TMP/server-env"
  echo PRIVATE_SYNTHETIC_SERVER_OUTPUT
  echo PRIVATE_SYNTHETIC_SERVER_ERROR >&2
  touch "$TEST_TMP/server-ready"
  exit 0
elif [[ "${1:-}" == '-' && -n "${REQUEST_WAV:-}" ]]; then
  TEST_TEXT="$TEST_TEXT" exec /usr/bin/python3 -c 'import json,os; print(json.dumps({"status":"error","error":"PRIVATE_SYNTHETIC_REQUEST_PATH"} if os.getenv("TEST_SERVER_ERROR") == "1" else {"status":"ok","text":os.environ["TEST_TEXT"]}))'
else
  if [[ "${1:-}" == -c && "${2:-}" == *'patterns ='* ]]; then
    printf '%s\0' "$@" >"$TEST_TMP/app-argv"
  fi
  exec /usr/bin/python3 "$@"
fi
EOF
cat >"$TMP/bin/ydotool" <<'EOF'
#!/usr/bin/env bash
if [[ "${1:-}" == type && "${2:-}" == --help ]]; then
  if [[ "${TEST_OLD_YDOTOOL:-0}" == 1 ]]; then echo '--key-hold'; else echo '--key-hold --file=PATH'; fi
  exit 0
fi
printf '%s\0' "$@" >"$TEST_TMP/backend-argv"
printf '%s\n' "$1" >>"$TEST_TMP/events"
if [[ "$1" == type ]]; then cat >"$TEST_TMP/typed"; fi
[[ "$1" != key || "${TEST_FAIL_KEY:-0}" != 1 ]] || exit 4
[[ "$1" != type || "${TEST_FAIL_TYPE:-0}" != 1 ]] || { echo PRIVATE_SYNTHETIC_BACKEND_ERROR >&2; exit 4; }
EOF
cat >"$TMP/bin/wtype" <<'EOF'
#!/usr/bin/env bash
printf '%s\0' "$@" >"$TEST_TMP/backend-argv"
[[ "$*" == '-' ]] || exit 4
printf 'type\n' >>"$TEST_TMP/events"
cat >"$TEST_TMP/typed"
EOF
cat >"$TMP/bin/xdotool" <<'EOF'
#!/usr/bin/env bash
printf '%s\0' "$@" >"$TEST_TMP/backend-argv"
[[ "${1:-}" == type ]] || exit 4
printf 'type\n' >>"$TEST_TMP/events"
cat >"$TEST_TMP/typed"
EOF
cat >"$TMP/bin/wl-copy" <<'EOF'
#!/usr/bin/env bash
[[ "${TEST_FAIL_CLIP:-0}" != 1 ]] || { echo PRIVATE_SYNTHETIC_CLIP_ERROR >&2; exit 1; }
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
  "desktopFile: ${TEST_DESKTOP_FILE:-org.kde.konsole}" "resourceClass: ${TEST_RESOURCE_CLASS:-konsole}" "caption: ${TEST_CAPTION:-test window}"
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
chmod 600 "$TMP/runtime/typing.sock"
# A fake socket outside the private runtime directory is never trusted.
/usr/bin/python3 - "$TMP/shared/untrusted.sock" <<'PY' &
import socket,sys,time
s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
s.bind(sys.argv[1]);s.listen(1);time.sleep(90)
PY
untrusted_pid=$!
for _ in {1..30}; do [[ -S "$TMP/shared/untrusted.sock" ]] && break; sleep 0.05; done
[[ -S "$TMP/shared/untrusted.sock" ]]
if grep -Fq '/tmp/.ydotool_socket' "$ROOT/bin/hermeskey"; then
  echo 'Shared ydotool socket fallback was reintroduced' >&2
  exit 1
fi

run_case() {
  local text="$1" copy="$2" shortcut="$3" backend="${4:-ydotool}"
  export TEST_TEXT="$text"
  printf '%s\n' 'OVERLAY_ENABLED=0' 'SOUND_ENABLED=0' 'INSERT_MODE=type' \
    "FOCUS_SAFE_MODE=${TEST_FOCUS_SAFE:-0}" "COPY_TO_CLIPBOARD=$copy" "TYPE_BACKEND=$backend" "RECORD_SOURCE=${TEST_SOURCE:-default}" "YDOTOOL_SOCKET_PATH=${TEST_SOCKET_OVERRIDE:-$TMP/runtime/typing.sock}" \
    "PASTE_SHORTCUT=$shortcut" >"$HERMESKEY_CONFIG"
  rm -f "$TMP/clipboard" "$TMP/events" "$TMP/notifications" "$TMP/typed" "$TMP/backend-argv" "$TMP/app-argv"
  "$ROOT/bin/hermeskey" >"$TMP/start-output" 2>"$TMP/start-errors"
  if [[ "${TEST_SWITCH_FOCUS:-0}" == 1 ]]; then
    TEST_UUID=22222222-2222-2222-2222-222222222222; export TEST_UUID
  fi
  "$ROOT/bin/hermeskey" >"$TMP/result" 2>"$TMP/stop-errors"
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
run_case 'hello123' 1 auto
[[ ! -e "$TMP/clipboard" && "$(<"$TMP/events")" == type ]]
grep -q 'clipboard backup failed' "$TMP/result"
unset TEST_FAIL_CLIP

run_case 'Привет мир' 0 auto
[[ ! -e "$TMP/clipboard" && ! -e "$TMP/events" ]]
grep -q 'not inserted or copied' "$TMP/result"
grep -q 'clipboard backup' "$TMP/notifications"

run_case 'hello123' 0 auto
[[ ! -e "$TMP/clipboard" ]]
[[ "$(<"$TMP/events")" == type && "$(<"$TMP/typed")" == hello123 ]]
grep -aFq -- '--file=-' "$TMP/backend-argv"
if grep -aFq -- 'hello123' "$TMP/backend-argv"; then echo 'Transcript in ydotool argv' >&2; exit 1; fi

run_case 'SYNTHETIC_WTYPE_TEXT' 0 auto wtype
[[ "$(<"$TMP/typed")" == SYNTHETIC_WTYPE_TEXT && ! -e "$TMP/clipboard" ]]
if grep -aFq -- 'SYNTHETIC_WTYPE_TEXT' "$TMP/backend-argv"; then echo 'Transcript in wtype argv' >&2; exit 1; fi

run_case 'SYNTHETIC_XDOTOOL_TEXT' 0 auto xdotool
[[ "$(<"$TMP/typed")" == SYNTHETIC_XDOTOOL_TEXT && ! -e "$TMP/clipboard" ]]
grep -aFq -- '--file' "$TMP/backend-argv"
if grep -aFq -- 'SYNTHETIC_XDOTOOL_TEXT' "$TMP/backend-argv"; then echo 'Transcript in xdotool argv' >&2; exit 1; fi

TEST_CAPTION=PRIVATE_SYNTHETIC_WINDOW_TITLE; export TEST_CAPTION
run_case 'hello123' 1 auto
[[ -e "$TMP/app-argv" ]]
if grep -aFq -- "$TEST_CAPTION" "$TMP/app-argv"; then echo 'Window caption in Python argv' >&2; exit 1; fi
unset TEST_CAPTION

TEST_OLD_YDOTOOL=1; export TEST_OLD_YDOTOOL
run_case 'hello123' 0 auto
[[ ! -e "$TMP/clipboard" && ! -e "$TMP/typed" ]]
grep -q 'cannot accept private text safely' "$TMP/notifications"
TEST_UNKNOWN=1; export TEST_UNKNOWN
run_case 'hello123' 1 auto
[[ "$(<"$TMP/clipboard")" == hello123 && ! -e "$TMP/typed" ]]
grep -q 'backend lacks private input' "$TMP/result"
unset TEST_UNKNOWN TEST_OLD_YDOTOOL

TEST_SOCKET_OVERRIDE="$TMP/runtime/absent.sock"
run_case 'hello123' 0 auto
[[ ! -e "$TMP/events" && ! -e "$TMP/clipboard" ]]

TEST_SOCKET_OVERRIDE="$TMP/shared/untrusted.sock"
run_case 'hello123' 0 auto
[[ ! -e "$TMP/events" && ! -e "$TMP/clipboard" ]]
grep -q 'socket unavailable or untrusted' "$TMP/notifications"
run_case 'hello123' 1 ctrl-v
[[ ! -e "$TMP/events" && "$(<"$TMP/clipboard")" == hello123 ]]
grep -q 'typing socket unavailable or untrusted' "$TMP/result"
run_case 'Français été' 1 ctrl-v
[[ ! -e "$TMP/events" && "$(<"$TMP/clipboard")" == 'Français été' ]]
grep -q 'paste shortcut failed' "$TMP/result"

ln -s "$TMP/shared/untrusted.sock" "$TMP/runtime/symlink.sock"
TEST_SOCKET_OVERRIDE="$TMP/runtime/symlink.sock"
run_case 'hello123' 0 auto
[[ ! -e "$TMP/events" && ! -e "$TMP/clipboard" ]]

TEST_SOCKET_OVERRIDE="$TMP/runtime/typing.sock"
chmod 666 "$TMP/runtime/typing.sock"
run_case 'hello123' 0 auto
[[ ! -e "$TMP/events" && ! -e "$TMP/clipboard" ]]
chmod 600 "$TMP/runtime/typing.sock"
chmod 755 "$TMP/runtime"
if "$ROOT/bin/hermeskey" >"$TMP/rejected"; then
  echo 'Recording started in a nonprivate runtime directory' >&2
  exit 1
fi
[[ ! -e "$TMP/runtime/hermeskey_recording.pid" ]]
chmod 700 "$TMP/runtime"
unset TEST_SOCKET_OVERRIDE
run_case 'hello123' 0 auto
[[ "$(<"$TMP/events")" == type && "$(<"$TMP/typed")" == hello123 ]]

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

# Emulate the shortcut's captured stdout/stderr (potential journal content)
# and the local runtime log with fake private app/device/path identifiers.
TEST_UUID=facefeed-dead-beef-babe-aaaabbbbcccc
TEST_DESKTOP_FILE=PRIVATE_SYNTHETIC_DESKTOP_ID
TEST_RESOURCE_CLASS=PRIVATE_SYNTHETIC_RESOURCE_CLASS
TEST_SOURCE=PRIVATE_SYNTHETIC_MICROPHONE_SOURCE
TEST_CAPTION=PRIVATE_SYNTHETIC_WINDOW_TITLE
export TEST_UUID TEST_DESKTOP_FILE TEST_RESOURCE_CLASS TEST_SOURCE TEST_CAPTION
TEST_FOCUS_SAFE=1 TEST_SWITCH_FOCUS=1; export TEST_FOCUS_SAFE TEST_SWITCH_FOCUS
run_case 'PRIVATE_SYNTHETIC_TRANSCRIPT_TEXT' 0 auto
[[ ! -e "$TMP/clipboard" && ! -e "$TMP/events" ]]
unset TEST_SWITCH_FOCUS TEST_FOCUS_SAFE
TEST_SERVER_ERROR=1; export TEST_SERVER_ERROR
run_case 'PRIVATE_SYNTHETIC_TRANSCRIPT_TEXT' 0 auto
unset TEST_SERVER_ERROR
TEST_FAIL_TYPE=1; export TEST_FAIL_TYPE
run_case 'PRIVATE_SYNTHETIC_TRANSCRIPT_TEXT' 0 auto
unset TEST_FAIL_TYPE
TEST_FAIL_CLIP=1; export TEST_FAIL_CLIP
run_case 'PRIVATE_SYNTHETIC_TRANSCRIPT_TEXT' 1 auto
unset TEST_FAIL_CLIP
run_case 'PRIVATE_SYNTHETIC_TRANSCRIPT_TEXT' 0 auto PRIVATE_SYNTHETIC_BACKEND_ID
run_case 'Français été' 1 PRIVATE_SYNTHETIC_SHORTCUT
# The standalone server fallback must still receive its model/socket settings,
# but must not persist its raw third-party output or create an unbounded log.
TEST_REQUIRE_SERVER_READY=1 MODEL=PRIVATE_SYNTHETIC_MODEL_ID
PYTHON_STT="$TMP/bin/python3" SERVER_SCRIPT="$TMP/hermeskey-server-fake.py"
export TEST_REQUIRE_SERVER_READY MODEL PYTHON_STT SERVER_SCRIPT
run_case 'PRIVATE_SYNTHETIC_TRANSCRIPT_TEXT' 0 auto
[[ -f "$TMP/server-env" && -f "$TMP/server-ready" ]]
grep -qF 'PRIVATE_SYNTHETIC_MODEL_ID' "$TMP/server-env"
[[ ! -e "$TMP/state/hermeskey/hermeskey-server.log" ]]
unset TEST_REQUIRE_SERVER_READY MODEL PYTHON_STT SERVER_SCRIPT
for private in PRIVATE_SYNTHETIC facefeed-dead-beef-babe-aaaabbbbcccc 'hello123' '你好'; do
  if grep -qF "$private" "$TMP/state/hermeskey/hermeskey.log" "$TMP/start-output" "$TMP/start-errors" "$TMP/stop-errors" "$TMP/result"; then
    echo 'Private content or identifying metadata leaked to runtime diagnostics' >&2
    exit 1
  fi
done
# An old unbounded log is discarded, rather than moved into an unbounded .1.
head -c 300000 /dev/zero | tr '\0' x >"$TMP/state/hermeskey/hermeskey.log"
run_case 'hello123' 0 auto
[[ $(stat -c %s "$TMP/state/hermeskey/hermeskey.log") -le 262144 ]]
[[ ! -e "$TMP/state/hermeskey/hermeskey.log.1" ]]
# A normally-sized log keeps at most one bounded backup.
head -c 262120 /dev/zero | tr '\0' x >"$TMP/state/hermeskey/hermeskey.log"
run_case 'hello123' 0 auto
[[ $(stat -c %s "$TMP/state/hermeskey/hermeskey.log") -le 262144 ]]
[[ $(stat -c %s "$TMP/state/hermeskey/hermeskey.log.1") -le 262144 ]]
printf 'Unicode insertion and private-log policy tests passed.\n'
