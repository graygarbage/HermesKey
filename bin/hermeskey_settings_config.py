"""Small, non-executing editor for GUI-managed .env settings.

Settings, the installed hotkey and both user services use ~/.config/hermeskey/hermeskey.env.
Everything we do not understand is left intact, not parsed or evaluated.
"""
import fcntl
import os
import re
import stat
import tempfile
from pathlib import Path
from typing import Callable

DEFAULTS = {
    "MODEL": "medium", "STT_LANG": "en", "RECORD_SOURCE": "default",
    "HERMESKEY_OFFLINE": "0", "INSERT_MODE": "type", "COPY_TO_CLIPBOARD": "1", "FOCUS_SAFE_MODE": "0",
    "OVERLAY_ENABLED": "1", "SOUND_ENABLED": "1",
}
SAFE_MODEL = re.compile(r"[A-Za-z0-9._/-]+\Z")
SAFE_LANGUAGE = re.compile(r"(?:[a-z]{2}|haw|yue)?\Z")
SAFE_SOURCE = re.compile(r"[A-Za-z0-9_./:@-]+\Z")
BEHAVIOR_FLAGS = {"HERMESKEY_OFFLINE", "COPY_TO_CLIPBOARD", "FOCUS_SAFE_MODE", "OVERLAY_ENABLED", "SOUND_ENABLED"}
MANAGED_KEYS = "|".join(DEFAULTS)
MANAGED = re.compile(rf"^[ \t]*(?:export[ \t]+)?({MANAGED_KEYS})[ \t]*=")
ASSIGNMENT = re.compile(
    rf"^(?P<prefix>[ \t]*(?P<key>{MANAGED_KEYS})=)"
    r"(?P<value>[A-Za-z0-9_./:@-]*|\"[A-Za-z0-9_./:@-]*\"|'[A-Za-z0-9_./:@-]*')"
    r"(?P<suffix>[ \t]*(?:\#.*)?)$"
)


class ConfigError(Exception):
    """Unsafe or unsupported config; do not write it."""


class ConfigChanged(ConfigError):
    """Config changed on disk after loading; user must reopen."""


def canonical_path() -> Path:
    # systemd's EnvironmentFile uses %h/.config, regardless of XDG_CONFIG_HOME.
    return Path.home() / ".config/hermeskey/hermeskey.env"


def parse_lines(text: str) -> tuple[list[str], dict[str, str], dict[str, int]]:
    lines = text.splitlines(keepends=True)
    values = dict(DEFAULTS)
    positions = {}
    for index, line in enumerate(lines):
        body = line.rstrip("\r\n")
        match = MANAGED.match(body)
        if not match:
            continue
        key = match.group(1)
        if key in positions:
            raise ConfigError(f"Duplicate {key} assignment on line {index + 1}; edit it manually")
        assignment = ASSIGNMENT.fullmatch(body)
        if assignment is None:
            raise ConfigError(f"Unsupported {key} assignment on line {index + 1}; edit it manually")
        raw = assignment.group("value")
        value = raw[1:-1] if raw.startswith(("'", '"')) else raw
        if (key == "INSERT_MODE" and value not in {"type", "clipboard"}) or (
            key in BEHAVIOR_FLAGS and value not in {"0", "1"}
        ):
            raise ConfigError(f"Unsupported {key} value on line {index + 1}; edit it manually")
        values[key] = value
        positions[key] = index
    return lines, values, positions


class ConfigDocument:
    def __init__(self, path: Path):
        self.path = path
        if path.is_symlink() or not path.is_file():
            raise ConfigError(f"Config must be a regular file: {path}")
        try:
            self.original = path.read_bytes()
            text = self.original.decode("utf-8")
        except (OSError, UnicodeError) as exc:
            raise ConfigError(f"Cannot read UTF-8 config: {path}") from exc
        _, self.values, _ = parse_lines(text)

    def render(self, edits: dict[str, str]) -> bytes:
        for key, value in edits.items():
            if key not in DEFAULTS:
                raise ConfigError(f"Unsupported GUI key: {key}")
            pattern = {"MODEL": SAFE_MODEL, "STT_LANG": SAFE_LANGUAGE, "RECORD_SOURCE": SAFE_SOURCE}.get(key)
            allowed = (
                bool(pattern.fullmatch(value)) if pattern else
                value in ({"type", "clipboard"} if key == "INSERT_MODE" else {"0", "1"})
            ) if isinstance(value, str) else False
            if not allowed:
                raise ConfigError(f"Invalid {key}; use a simple literal without spaces, quotes or shell syntax")
        lines, _, positions = parse_lines(self.original.decode("utf-8"))
        for key, value in edits.items():
            if key in positions:
                index = positions[key]
                line = lines[index]
                ending = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
                match = ASSIGNMENT.fullmatch(line.rstrip("\r\n"))
                lines[index] = f'{match.group("prefix")}{value}{match.group("suffix")}{ending}'
            else:
                if lines and not lines[-1].endswith(("\n", "\r")):
                    lines[-1] += "\n"
                lines.append(f"{key}={value}\n")
        return "".join(lines).encode("utf-8")

    def save(self, edits: dict[str, str], validator: Callable[[Path], None]) -> None:
        content = self.render(edits)
        if content == self.original:
            return
        lock_path = self.path.with_name(self.path.name + ".lock")
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        tmp_path = None
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            if self.path.is_symlink() or not self.path.is_file() or self.path.read_bytes() != self.original:
                raise ConfigChanged("Config changed outside Settings; reopen it to avoid overwriting edits")
            fd, tmp_name = tempfile.mkstemp(prefix=".hermeskey-env-", dir=self.path.parent)
            tmp_path = Path(tmp_name)
            with os.fdopen(fd, "wb") as stream:
                os.fchmod(stream.fileno(), stat.S_IRUSR | stat.S_IWUSR)
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            validator(tmp_path)
            # Other editors do not take our advisory lock; recheck after the
            # potentially slow validator, immediately before replacing.
            if self.path.is_symlink() or not self.path.is_file() or self.path.read_bytes() != self.original:
                raise ConfigChanged("Config changed while validating; reopen it to avoid overwriting edits")
            os.replace(tmp_path, self.path)
            tmp_path = None
            directory_fd = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
            self.original = content
            _, self.values, _ = parse_lines(content.decode("utf-8"))
        finally:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)
            os.close(lock_fd)
