#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")/.."
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/home/.config/hermeskey" "$tmp/xdg/hermeskey" "$tmp/venv/bin"
export HOME="$tmp/home" XDG_CONFIG_HOME="$tmp/xdg"
printf '#!/usr/bin/env bash\nexit 0\n' >"$tmp/venv/bin/python"
chmod +x "$tmp/venv/bin/python"

# Defaults use the canonical file, not a custom-XDG location.
bash scripts/check-config.sh "$tmp/venv" >/dev/null
canonical="$HOME/.config/hermeskey/hermeskey.env"
legacy="$XDG_CONFIG_HOME/hermeskey/hermeskey.env"
printf 'PYTHON_STT="%s"\n' "$tmp/missing/python" >"$canonical"
if bash scripts/check-config.sh "$tmp/venv" >"$tmp/output" 2>&1; then
  echo 'Expected missing PYTHON_STT to fail' >&2
  exit 1
fi
grep -q 'Configured speech Python does not exist' "$tmp/output"
printf 'PYTHON_STT="%s"\n' "$tmp/venv/bin/python" >"$canonical"
bash scripts/check-config.sh "$tmp/venv" >/dev/null

# Before a migration, the checker examines a legacy custom-XDG config as
# plain text, never executes its shell lines, and respects its custom venv.
rm "$canonical"
# shellcheck disable=SC2016  # literal synthetic shell code must not run
printf 'PYTHON_STT="%s"\nUNRELATED=$(touch "%s")\n' "$tmp/venv/bin/python" "$tmp/should-not-run" >"$legacy"
bash scripts/check-config.sh "$tmp/venv" >/dev/null
[[ ! -e "$tmp/should-not-run" ]]
printf 'PYTHON_STT="%s"\n' "$tmp/missing/python" >"$legacy"
if bash scripts/check-config.sh "$tmp/venv" >"$tmp/output" 2>&1; then
  echo 'Expected invalid legacy custom venv to fail' >&2
  exit 1
fi
grep -q 'Configured speech Python does not exist' "$tmp/output"
printf 'PYTHON_STT="%s"\n' "$tmp/venv/bin/python" >"$legacy"
cp "$legacy" "$canonical"
bash scripts/check-config.sh "$tmp/venv" >/dev/null
printf 'MODEL=small\n' >>"$canonical"
if bash scripts/check-config.sh "$tmp/venv" >"$tmp/output" 2>&1; then
  echo 'Expected conflicting configs to fail' >&2
  exit 1
fi
grep -q 'Conflicting canonical and custom-XDG' "$tmp/output"
rm "$legacy"
# shellcheck disable=SC2016  # verify expansions are rejected, not executed
printf 'PYTHON_STT="$(touch bad)"\n' >"$canonical"
if bash scripts/check-config.sh "$tmp/venv" >"$tmp/output" 2>&1; then
  echo 'Expected shell expansion in PYTHON_STT to be rejected' >&2
  exit 1
fi
grep -q 'literal absolute path' "$tmp/output"
[[ ! -e "$tmp/should-not-run" ]]
printf 'Preserved-config checks passed.\n'
