"""Bounded, local-only systemd and socket diagnostics for the Settings panel."""
import argparse
import json
import os
import re
import socket
import subprocess
from pathlib import Path

UNITS = ("hermeskey.service", "hermeskey-ydotoold.service")
MAX_REPORT = 65536


def unit_state(unit: str) -> dict:
    if unit not in UNITS:
        raise ValueError("Unknown service")
    try:
        result = subprocess.run(
            ["systemctl", "--user", "show", unit, "--property=LoadState,ActiveState,SubState,Result", "--no-pager"],
            capture_output=True, text=True, timeout=3, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"active": "unknown", "sub": "", "result": "", "ready": False}
    if result.returncode:
        return {"active": "unknown", "sub": "", "result": "", "ready": False}
    props = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    active = "not installed" if props.get("LoadState") == "not-found" else props.get("ActiveState", "unknown")
    return {"active": active, "sub": props.get("SubState", ""),
            "result": props.get("Result", ""), "ready": False}


def speech_socket() -> str | None:
    default = os.path.join(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"), "hermeskey.sock")
    config = Path.home() / ".config/hermeskey/hermeskey.env"
    try:
        lines = config.read_text().splitlines()
    except (OSError, UnicodeError):
        return default
    custom = []
    for line in lines:
        if re.match(r"^\s*SOCK\s*=", line):
            custom.append(line.split("=", 1)[1].strip().strip("\"'"))
    if not custom:
        return default
    # Do not evaluate shell expressions. Unknown paths have unknown readiness.
    return custom[0] if len(custom) == 1 and re.fullmatch(r"/[A-Za-z0-9_./-]+", custom[0]) else None


def probe_speech(path: str | None) -> bool | None:
    if path is None:
        return None
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(0.5)
            conn.connect(path)
            conn.sendall(b'{"cmd":"ping"}\n')
            reply = json.loads(conn.recv(4096).decode("utf-8"))
        return reply.get("status") == "ok" and reply.get("ready") is True
    except (OSError, ValueError):
        return False


def probe_ydotool() -> bool:
    path = os.path.join(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"), ".ydotool_socket")
    try:
        # ydotoold uses a Unix datagram socket, not the speech server's stream.
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as conn:
            conn.settimeout(0.5)
            conn.connect(path)
        return True
    except OSError:
        return False


def statuses() -> dict:
    result = {unit: unit_state(unit) for unit in UNITS}
    if result[UNITS[0]]["active"] == "active":
        result[UNITS[0]]["ready"] = probe_speech(speech_socket())
    if result[UNITS[1]]["active"] == "active":
        result[UNITS[1]]["ready"] = probe_ydotool()
    return result


def logs() -> str:
    runtime_path = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "hermeskey/hermeskey.log"
    try:
        with runtime_path.open("rb") as stream:
            stream.seek(0, os.SEEK_END)
            offset = max(0, stream.tell() - 16384)
            stream.seek(offset)
            if offset:
                stream.readline()  # avoid showing a truncated log line
            runtime = stream.read(16384).decode("utf-8", errors="replace")
    except OSError:
        runtime = "No local runtime log found."
    try:
        result = subprocess.run(
            ["journalctl", "--user", "-u", UNITS[0], "-u", UNITS[1], "-n", "80", "--no-pager"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        journal = result.stdout if result.returncode == 0 else "Could not read user journal."
    except (OSError, subprocess.TimeoutExpired):
        journal = "Could not read user journal."
    return ("== HermesKey runtime log (local only) ==\n" + runtime +
            "\n== User service journal (review before sharing) ==\n" + journal)[-MAX_REPORT:]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("status", "logs"))
    args = parser.parse_args()
    print(json.dumps(statuses()) if args.action == "status" else logs())


if __name__ == "__main__":
    main()
