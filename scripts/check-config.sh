#!/usr/bin/env bash
# Check the interpreter that the installed speech service will actually use.
# Never source a preserved (possibly legacy) config during bootstrap.
set -euo pipefail

venv_dir="$1"
config_file="$HOME/.config/hermeskey/hermeskey.env"
if [[ -L "$HOME/.config/hermeskey" || -L "$config_file" ]]; then
  printf 'Refusing symlinked canonical HermesKey config.\n' >&2
  exit 1
fi
if [[ -n "${XDG_CONFIG_HOME:-}" ]]; then
  [[ "$XDG_CONFIG_HOME" == /* ]] || { printf 'XDG_CONFIG_HOME must be absolute.\n' >&2; exit 1; }
  legacy="${XDG_CONFIG_HOME%/}/hermeskey/hermeskey.env"
  if [[ "$legacy" != "$config_file" && ! "$legacy" -ef "$config_file" && -e "$legacy" ]]; then
    if [[ -L "$XDG_CONFIG_HOME" || -L "${legacy%/*}" || -L "$legacy" || ! -f "$legacy" ]]; then
      printf 'Invalid or symlinked legacy HermesKey config.\n' >&2
      exit 1
    fi
    if [[ -e "$config_file" ]]; then
      if ! cmp -s -- "$config_file" "$legacy"; then
        printf 'Conflicting canonical and custom-XDG HermesKey configs; choose one before upgrading.\n' >&2
        exit 1
      fi
    else
      config_file="$legacy"
    fi
  fi
fi

python_stt="$venv_dir/bin/python"
if [[ -f "$config_file" ]]; then
  [[ ! -L "$config_file" ]] || { printf 'Refusing symlinked HermesKey config.\n' >&2; exit 1; }
  python_stt="$(HERMESKEY_CHECK_CONFIG="$config_file" HERMESKEY_DEFAULT_PYTHON="$python_stt" python3 - <<'PY'
import os
import re
import sys
from pathlib import Path

try:
    lines = Path(os.environ["HERMESKEY_CHECK_CONFIG"]).read_text(encoding="utf-8").splitlines()
except (OSError, UnicodeError):
    sys.exit("Cannot read HermesKey config; inspect it privately.")
value = None
for line in lines:
    if not re.match(r"^\s*(?:export\s+)?PYTHON_STT\s*=", line):
        continue
    # Both Bash and systemd must consume the same literal value. Do not eval
    # variables, shell expressions or an `export` line systemd would ignore.
    match = re.fullmatch(r"\s*PYTHON_STT=(?:\"([^\"]*)\"|'([^']*)'|([^\s#]*))(?:\s+#.*)?\s*", line)
    if value is not None or match is None:
        sys.exit("Unsupported or duplicate PYTHON_STT assignment; use a single literal path.")
    value = next(part for part in match.groups() if part is not None)
    if value and not re.fullmatch(r"/[A-Za-z0-9_./ +@-]+", value):
        sys.exit("PYTHON_STT must be a literal absolute path without shell expansion.")
print(value or os.environ["HERMESKEY_DEFAULT_PYTHON"])
PY
)"
fi

if [[ ! -x "$python_stt" ]]; then
  printf 'Configured speech Python does not exist. Check PYTHON_STT in the canonical config (or legacy custom-XDG config before migration).\n' >&2
  exit 1
fi
if ! "$python_stt" -c 'import faster_whisper' >/dev/null 2>&1; then
  printf 'Configured speech Python cannot import faster_whisper. Check its installed requirements privately.\n' >&2
  exit 1
fi
printf 'Speech Python ready.\n'
