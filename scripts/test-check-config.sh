#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")/.."
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/hermeskey" "$tmp/venv/bin"
printf '#!/usr/bin/env bash\nexit 0\n' >"$tmp/venv/bin/python"
chmod +x "$tmp/venv/bin/python"

XDG_CONFIG_HOME="$tmp" bash scripts/check-config.sh "$tmp/venv" >/dev/null
printf 'PYTHON_STT="%s"\n' "$tmp/missing/python" >"$tmp/hermeskey/hermeskey.env"
if XDG_CONFIG_HOME="$tmp" bash scripts/check-config.sh "$tmp/venv" >"$tmp/output" 2>&1; then
  echo 'Expected missing PYTHON_STT to fail' >&2
  exit 1
fi
grep -q 'Configured speech Python does not exist' "$tmp/output"

printf 'PYTHON_STT="%s"\n' "$tmp/venv/bin/python" >"$tmp/hermeskey/hermeskey.env"
XDG_CONFIG_HOME="$tmp" bash scripts/check-config.sh "$tmp/venv" >/dev/null
printf 'Preserved-config checks passed.\n'
