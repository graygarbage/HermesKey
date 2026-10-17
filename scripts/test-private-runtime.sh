#!/usr/bin/env bash
# Exercise unsafe paths and forged PID state without a microphone or real service.
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")/.."
root="$PWD"
tmp="$(mktemp -d)"
cleanup() {
  if [[ -n "${sleeper:-}" ]]; then kill "$sleeper" 2>/dev/null || true; fi
  rm -rf "$tmp"
}
trap cleanup EXIT
mkdir -p "$tmp/private" "$tmp/shared" "$tmp/bin" "$tmp/state"
chmod 700 "$tmp/private"
chmod 777 "$tmp/shared"
printf '%s\n' 'OVERLAY_ENABLED=0' 'SOUND_ENABLED=0' 'COPY_TO_CLIPBOARD=0' >"$tmp/config.env"
cat >"$tmp/bin/notify-send" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
cat >"$tmp/bin/ffmpeg" <<'EOF'
#!/usr/bin/env bash
printf 'unexpected recorder start\n' >>"$TEST_TMP/ffmpeg-started"
exit 1
EOF
chmod +x "$tmp/bin/"*
export TEST_TMP="$tmp" PATH="$tmp/bin:$PATH" XDG_STATE_HOME="$tmp/state" HERMESKEY_CONFIG="$tmp/config.env"

if XDG_RUNTIME_DIR="$tmp/shared" "$root/bin/hermeskey" >"$tmp/output"; then
  echo 'Recording allowed in shared runtime directory' >&2; exit 1
fi
[[ ! -e "$tmp/shared/hermeskey_recording.pid" && ! -e "$tmp/ffmpeg-started" ]]

if XDG_RUNTIME_DIR="$tmp/private" WAV="$tmp/shared/audio.wav" "$root/bin/hermeskey" >"$tmp/output"; then
  echo 'Recording allowed with shared audio override' >&2; exit 1
fi
[[ ! -e "$tmp/shared/audio.wav" && ! -e "$tmp/ffmpeg-started" ]]

printf 'unchanged' >"$tmp/shared/target"
ln -s "$tmp/shared/target" "$tmp/private/hermeskey_audio.wav"
if XDG_RUNTIME_DIR="$tmp/private" "$root/bin/hermeskey" >"$tmp/output"; then
  echo 'Recording allowed with symlinked audio' >&2; exit 1
fi
[[ "$(<"$tmp/shared/target")" == unchanged && ! -e "$tmp/ffmpeg-started" ]]
rm "$tmp/private/hermeskey_audio.wav"

sleep 30 &
sleeper=$!
printf '%s:0\n' "$sleeper" >"$tmp/private/hermeskey_recording.pid"
chmod 600 "$tmp/private/hermeskey_recording.pid"
XDG_RUNTIME_DIR="$tmp/private" "$root/bin/hermeskey" --locked-toggle >"$tmp/output"
kill -0 "$sleeper" 2>/dev/null
[[ ! -e "$tmp/private/hermeskey_recording.pid" && ! -e "$tmp/ffmpeg-started" ]]
grep -q 'no process signaled' "$tmp/output"
printf 'Private runtime and PID state tests passed.\n'
