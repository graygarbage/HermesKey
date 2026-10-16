#!/usr/bin/env bash
# Repository checks. Used by `make check` and CI.
set -euo pipefail

cd "$(dirname -- "${BASH_SOURCE[0]}")/.."

# Every bash script in the repo, found by shebang so new scripts are
# covered automatically.
shell_scripts=(install.sh uninstall.sh scripts/*.sh)
for f in bin/*; do
  [[ -f "$f" && "$f" != *.py ]] || continue
  if head -n1 "$f" | grep -q 'bash'; then
    shell_scripts+=("$f")
  fi
done

echo "Shell syntax (${#shell_scripts[@]} scripts)"
bash -n "${shell_scripts[@]}"

echo "Python syntax"
python3 -m py_compile bin/hermeskey-server.py bin/hermeskey-overlay.py scripts/verify-install.py
python3 -m unittest discover -s tests -p 'test_*.py'

echo "systemd units"
systemd-analyze --user verify systemd/user/hermeskey.service systemd/user/hermeskey-ydotoold.service

echo "Hotkey concurrency"
bash scripts/test-toggle-lock.sh

echo "Preserved config"
bash scripts/test-check-config.sh

if command -v shellcheck >/dev/null 2>&1; then
  echo "shellcheck"
  shellcheck "${shell_scripts[@]}"
elif [[ "${REQUIRE_SHELLCHECK:-0}" == "1" ]]; then
  echo 'shellcheck is required but not installed' >&2
  exit 1
else
  echo 'shellcheck not installed; skipping'
fi

echo 'All checks passed.'
