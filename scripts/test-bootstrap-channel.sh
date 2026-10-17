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
exit 22
EOF
cat >"$tmp/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
printf 'unexpected systemctl call\n' >>"$TEST_TMP/systemctl-calls"
exit 1
EOF
chmod +x "$tmp/bin/curl" "$tmp/bin/systemctl"
export TEST_TMP="$tmp" HOME="$tmp/home" PATH="$tmp/bin:$PATH"

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
printf 'Bootstrap release-channel tests passed.\n'
