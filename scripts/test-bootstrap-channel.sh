#!/usr/bin/env bash
# An unavailable release must not silently install mutable main. No network or services.
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")/.."
root="$PWD"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/bin" "$tmp/home"
cat >"$tmp/bin/curl" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"$TEST_TMP/curl-requests"
if [[ "${TEST_CURL_MODE:-}" == tampered ]]; then
  if [[ "$*" == *'/releases/latest'* ]]; then
    printf '{"tag_name":"%s","assets":[{"name":"hermeskey-%s.tar.gz","browser_download_url":"https://untrusted.invalid/asset.tar.gz"}]}\n' \
      "${TEST_TAG:-v0.6.4}" "${TEST_VERSION:-0.6.4}"
    exit 0
  fi
  for ((i=1; i<=$#; i++)); do
    if [[ "${!i}" == '-o' ]]; then
      next=$((i+1))
      printf 'SYNTHETIC_TAMPERED_ARCHIVE\n' >"${!next}"
      exit 0
    fi
  done
fi
exit 22
EOF
cat >"$tmp/bin/tar" <<'EOF'
#!/usr/bin/env bash
printf 'unexpected extraction\n' >>"$TEST_TMP/tar-calls"
exit 1
EOF
cat >"$tmp/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
printf 'unexpected systemctl call\n' >>"$TEST_TMP/systemctl-calls"
exit 1
EOF
chmod +x "$tmp/bin/curl" "$tmp/bin/tar" "$tmp/bin/systemctl"
export TEST_TMP="$tmp" HOME="$tmp/home" PATH="$tmp/bin:$PATH" XDG_RUNTIME_DIR="$tmp/runtime"
mkdir -p "$XDG_RUNTIME_DIR"
printf 'synthetic pid state\n' >"$XDG_RUNTIME_DIR/hermeskey_recording.pid"
if bash "$root/scripts/bootstrap.sh" --main >"$tmp/output" 2>&1; then
  echo 'Bootstrap continued during active recording' >&2
  exit 1
fi
grep -q 'Finish dictation before upgrading' "$tmp/output"
[[ ! -e "$tmp/curl-requests" && ! -e "$tmp/systemctl-calls" ]]
rm "$XDG_RUNTIME_DIR/hermeskey_recording.pid"

if bash "$root/scripts/bootstrap.sh" >"$tmp/output" 2>&1; then
  echo 'Bootstrap succeeded without a release asset' >&2
  exit 1
fi
grep -q 'refusing to install from main' "$tmp/output"
grep -q 'api.github.com/repos/graygarbage/HermesKey/releases/latest' "$tmp/curl-requests"
[[ "$(wc -l <"$tmp/curl-requests")" -eq 1 && ! -e "$tmp/systemctl-calls" ]]

rm "$tmp/curl-requests"
if bash "$root/scripts/bootstrap.sh" --main >"$tmp/output" 2>&1; then
  echo 'Bootstrap succeeded without the requested main archive' >&2
  exit 1
fi
grep -q 'github.com/graygarbage/HermesKey/archive/refs/heads/main.tar.gz' "$tmp/curl-requests"
[[ "$(wc -l <"$tmp/curl-requests")" -eq 1 && ! -e "$tmp/systemctl-calls" ]]
if grep -q 'api.github.com' "$tmp/curl-requests"; then
  echo 'Explicit --main unexpectedly queried latest release' >&2
  exit 1
fi
# A malicious/mismatched release cannot reach tar or install, even if the
# release API supplies a different browser_download_url.
rm "$tmp/curl-requests"
export TEST_CURL_MODE=tampered
if bash "$root/scripts/bootstrap.sh" >"$tmp/output" 2>&1; then
  echo 'Bootstrap accepted a tampered release archive' >&2
  exit 1
fi
grep -q 'Release archive digest mismatch' "$tmp/output"
grep -q 'releases/download/v0.6.4/hermeskey-0.6.4.tar.gz' "$tmp/curl-requests"
if grep -q 'untrusted.invalid' "$tmp/curl-requests"; then
  echo 'Bootstrap trusted an API-controlled asset URL' >&2
  exit 1
fi
[[ ! -e "$tmp/tar-calls" && ! -e "$tmp/systemctl-calls" ]]

# Previously reviewed v0.6.3 remains accepted (but tampering still fails).
rm "$tmp/curl-requests"
TEST_TAG=v0.6.3 TEST_VERSION=0.6.3 bash "$root/scripts/bootstrap.sh" >"$tmp/output" 2>&1 && {
  echo 'Bootstrap accepted a tampered legacy release' >&2
  exit 1
}
grep -q 'Release archive digest mismatch' "$tmp/output"
grep -q 'releases/download/v0.6.3/hermeskey-0.6.3.tar.gz' "$tmp/curl-requests"
[[ ! -e "$tmp/tar-calls" && ! -e "$tmp/systemctl-calls" ]]

# A newer published version without a reviewed, pinned digest must fail
# before downloading an archive, even though the API is reachable.
rm "$tmp/curl-requests"
TEST_TAG=v0.6.5 TEST_VERSION=0.6.5 bash "$root/scripts/bootstrap.sh" >"$tmp/output" 2>&1 && {
  echo 'Bootstrap accepted an unreviewed release' >&2
  exit 1
}
grep -q 'no reviewed digest' "$tmp/output"
[[ "$(wc -l <"$tmp/curl-requests")" -eq 1 && ! -e "$tmp/tar-calls" && ! -e "$tmp/systemctl-calls" ]]
printf 'Bootstrap release-channel and archive-integrity tests passed.\n'
