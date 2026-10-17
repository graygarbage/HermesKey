#!/usr/bin/env python3
"""Wait for the warm speech server and transcribe a bundled, synthetic voice clip.

No microphone or desktop input is touched. Used by bootstrap after install.sh;
can also be run by hand after a manual install from a repository checkout.
"""
import argparse
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path


def request(path: str, payload: dict, timeout: float = 5) -> dict:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
        conn.settimeout(timeout)
        conn.connect(path)
        conn.sendall((json.dumps(payload) + "\n").encode())
        data = bytearray()
        while b"\n" not in data:
            chunk = conn.recv(65536)
            if not chunk:
                break
            data.extend(chunk)
    return json.loads(data.decode())


def verify(socket_path: str, sample: Path, model_timeout: int, smoke_timeout: int) -> None:
    deadline = time.monotonic() + model_timeout
    offline = os.environ.get("HERMESKEY_OFFLINE", "0") == "1"
    phase = "offline speech model to load" if offline else "speech model to load/download"
    print(f"Waiting up to {model_timeout}s for {phase}...", flush=True)
    last_message = 0.0
    while True:
        try:
            reply = request(socket_path, {"cmd": "ping"})
            if reply.get("status") == "ok" and reply.get("ready"):
                break
        except (OSError, ValueError):
            pass  # Socket only appears after model load finishes.
        if time.monotonic() >= deadline:
            if offline:
                raise RuntimeError("offline model not ready; cache it first or select a local model path")
            raise RuntimeError("speech server did not become ready before the timeout")
        if time.monotonic() - last_message >= 15:
            message = ("Offline model not ready; cache it first or select a local model path."
                       if offline else "Model not ready yet; first run may download from Hugging Face...")
            print(message, flush=True)
            last_message = time.monotonic()
        time.sleep(2)

    print("Speech model ready. Running synthetic-audio transcription smoke test...", flush=True)
    reply = request(socket_path, {"cmd": "transcribe", "wav": str(sample), "language": "en"}, smoke_timeout)
    if reply.get("status") != "ok":
        # Third-party error details may contain sample paths or private text.
        raise RuntimeError("transcription failed; check local service diagnostics")
    text = reply.get("text", "")
    # The synthesized clip says "This is a test of Hermes Key speech recognition."
    # Whisper may spell the product name differently, but should get these words.
    if not all(re.search(rf"\b{word}\b", text, re.IGNORECASE) for word in ("test", "speech")):
        raise RuntimeError("smoke transcript did not contain expected words")
    print("Speech smoke test passed.", flush=True)

    if subprocess.run(["systemctl", "--user", "is-active", "--quiet", "hermeskey-ydotoold.service"]).returncode:
        raise RuntimeError("ydotoold user service is not active (speech test passed, but typing may fail)")
    print("ydotoold is active. Check microphone input and typing into your app manually.", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--socket", default=os.path.join(
        os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}", "hermeskey.sock"
    ))
    parser.add_argument("--sample", type=Path, default=Path(__file__).resolve().parent.parent / "tests/smoke.wav")
    parser.add_argument("--model-timeout", type=int, default=600)
    parser.add_argument("--smoke-timeout", type=int, default=180)
    args = parser.parse_args()
    if not args.sample.is_file():
        parser.error("smoke sample missing")
    try:
        verify(args.socket, args.sample.resolve(), args.model_timeout, args.smoke_timeout)
    except (RuntimeError, OSError, ValueError) as exc:
        # Only our own RuntimeErrors contain known, non-content messages.
        reason = str(exc) if type(exc) is RuntimeError else type(exc).__name__
        print(f"Install validation failed: {reason}", file=sys.stderr)
        print("Inspect: journalctl --user -u hermeskey.service -n 80 --no-pager", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
