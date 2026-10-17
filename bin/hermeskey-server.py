#!/usr/bin/env python3
import argparse
import json
import logging
import os
import re
import signal
import socket
import stat
import sys

# huggingface_hub reads offline/telemetry settings during import. Set them
# before loading faster-whisper; no dictated audio or transcript is sent there.
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
if os.environ.get("HERMESKEY_OFFLINE", "0") not in ("0", "1"):
    raise SystemExit("Invalid HERMESKEY_OFFLINE flag; use 0 or 1")
if os.environ.get("HERMESKEY_OFFLINE", "0") == "1":
    os.environ["HF_HUB_OFFLINE"] = "1"

from faster_whisper import WhisperModel


# Do not forward third-party HTTP/model logs to the user journal. Even INFO
# records may contain request URLs or private model/audio metadata. Only our
# allowlisted, sanitized diagnostics reach the service's stderr.
logging.basicConfig(level=logging.CRITICAL + 1, handlers=[logging.NullHandler()], force=True)
logger = logging.getLogger("hermeskey.server")
logger.setLevel(logging.INFO)
logger.propagate = False
safe_handler = logging.StreamHandler()
safe_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(safe_handler)


def log(msg: str) -> None:
    logger.info("%s", msg)


def validate_private_socket(path: str) -> None:
    """Never bind/unlink a socket in a shared directory or follow a symlink."""
    directory = os.path.dirname(path)
    parent = os.lstat(directory)
    if not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.getuid() or parent.st_mode & 0o077:
        raise ValueError("Speech socket needs a private user-owned runtime directory")
    try:
        existing = os.lstat(path)
    except FileNotFoundError:
        return
    if not stat.S_ISSOCK(existing.st_mode) or existing.st_uid != os.getuid() or existing.st_mode & 0o077:
        raise ValueError("Speech socket path is not a private user-owned socket")


def log_failure(stage: str, exc: Exception) -> None:
    """Log diagnostics, never str(exc), traceback source lines or local variables.

    Third-party exception messages may contain audio paths or user text. Python's
    normal traceback formatter includes that message and full source paths too.
    """
    def safe(value: str) -> str:
        return re.sub(r"[^A-Za-z0-9_.-]", "_", value)[:64]

    frames = []
    tb = exc.__traceback__
    while tb is not None:
        code = tb.tb_frame.f_code
        frames.append(f"{safe(os.path.basename(code.co_filename))}:{tb.tb_lineno}:{safe(code.co_name)}")
        tb = tb.tb_next
    location = " <- ".join(frames[-8:]) if frames else "unknown"
    logger.error("Server %s failed: %s at %s", stage, safe(type(exc).__name__), location)


class Server:
    def __init__(self, socket_path: str, model_name: str, language: str):
        self.socket_path = socket_path
        self.model_name = model_name
        self.language = language
        self.offline = os.environ.get("HERMESKEY_OFFLINE", "0") == "1"
        self.model = None
        self._sock = None
        self._bound_socket = False
        self._running = True

    def load(self) -> None:
        # Custom model IDs and paths may contain private names.
        log("loading speech model")
        try:
            self.model = WhisperModel(self.model_name, device="cpu", compute_type="int8",
                                      local_files_only=self.offline)
        except Exception:
            if self.offline:
                log("Offline model unavailable; cache it during an explicit online setup or use a local model path")
            raise
        log("model loaded")

    def cleanup(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:
                pass
        if self._bound_socket:
            try:
                os.unlink(self.socket_path)
            except FileNotFoundError:
                pass
            except Exception as e:
                log_failure("socket cleanup", e)
            finally:
                self._bound_socket = False

    def handle(self, request: dict) -> dict:
        cmd = request.get("cmd")
        if cmd == "ping":
            return {
                "status": "ok",
                "model": self.model_name,
                "language": self.language,
                "ready": self.model is not None,
            }

        if cmd != "transcribe":
            return {"status": "error", "error": "unknown command"}

        wav_path = request.get("wav")
        language = request.get("language", self.language)
        if not wav_path:
            return {"status": "error", "error": "missing wav"}
        if not os.path.exists(wav_path):
            return {"status": "error", "error": "wav not found"}

        segments, info = self.model.transcribe(
            wav_path,
            language=(language.strip() or None) if isinstance(language, str) else None,
        )
        text = " ".join(s.text.strip() for s in segments).strip()
        return {
            "status": "ok",
            "text": text,
            "language": getattr(info, "language", None),
            "duration": getattr(info, "duration", None),
        }

    def process(self, data: bytes) -> dict:
        try:
            raw = data.decode("utf-8", errors="replace").strip()
            if not raw:
                return {"status": "error", "error": "empty request"}
            return self.handle(json.loads(raw))
        except Exception as e:
            log_failure("request", e)
            return {"status": "error", "error": "server request failed; see hermeskey.service journal"}

    def serve(self) -> None:
        validate_private_socket(self.socket_path)
        # Remove only an existing, validated socket owned by this user. Never
        # unlink a path merely because a rejected config points at it.
        if os.path.lexists(self.socket_path):
            os.unlink(self.socket_path)
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock = sock
        # Create the socket file with owner-only permissions from the start.
        # Calling chmod() after bind() leaves a window where another local user
        # could connect (relevant when falling back to a shared dir like /tmp).
        old_umask = os.umask(0o177)
        try:
            sock.bind(self.socket_path)
            self._bound_socket = True
        finally:
            os.umask(old_umask)
        os.chmod(self.socket_path, 0o600)
        sock.listen(5)
        log("listening on local socket")

        while self._running:
            try:
                conn, _ = sock.accept()
            except OSError:
                break
            with conn:
                try:
                    data = b""
                    while True:
                        chunk = conn.recv(65536)
                        if not chunk:
                            break
                        data += chunk
                        if b"\n" in chunk:
                            break
                    response = self.process(data)
                    conn.sendall((json.dumps(response, ensure_ascii=False) + "\n").encode("utf-8"))
                except OSError as e:
                    log_failure("client connection", e)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--socket",
        default=os.environ.get("SOCK") or os.path.join(
            os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}", "hermeskey.sock"
        ),
    )
    parser.add_argument("--model", default=os.environ.get("MODEL", "medium"))
    parser.add_argument("--lang", default=os.environ.get("STT_LANG", "en"))
    args = parser.parse_args()

    server = Server(args.socket, args.model, args.lang)

    def stop(*_args):
        server._running = False
        server.cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    try:
        validate_private_socket(args.socket)
        server.load()
        server.serve()
    except Exception as e:
        log_failure("startup", e)
        return 1
    finally:
        server.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
