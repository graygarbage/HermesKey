"""System actions are fixed user units and readiness needs live sockets."""
import socket
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
import hermeskey_system_tools as tools


class SystemToolsTests(unittest.TestCase):
    def test_fixed_user_service_query_and_failure(self):
        with self.assertRaises(ValueError):
            tools.unit_state("arbitrary.service")
        with patch.object(tools.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="ActiveState=active\nSubState=running\nResult=success\n")) as run:
            info = tools.unit_state(tools.UNITS[0])
        self.assertEqual(info["active"], "active")
        self.assertEqual(run.call_args.args[0][:3], ["systemctl", "--user", "show"])
        with patch.object(tools.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="LoadState=not-found\nActiveState=inactive\n")):
            self.assertEqual(tools.unit_state(tools.UNITS[1])["active"], "not installed")
        with patch.object(tools.subprocess, "run", side_effect=tools.subprocess.TimeoutExpired("systemctl", 3)):
            self.assertEqual(tools.unit_state(tools.UNITS[0])["active"], "unknown")

    def test_status_requires_ping_not_just_active(self):
        active = lambda unit: {"active": "active", "sub": "running", "result": "success", "ready": False}
        with patch.object(tools, "unit_state", side_effect=active), \
             patch.object(tools, "speech_socket", return_value=None), \
             patch.object(tools, "probe_ydotool", return_value=False):
            states = tools.statuses()
        self.assertIsNone(states[tools.UNITS[0]]["ready"])
        self.assertFalse(states[tools.UNITS[1]]["ready"])

    def test_ydotool_uses_datagram_socket(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".ydotool_socket"
            with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as daemon:
                daemon.bind(str(path))
                with patch.dict(tools.os.environ, {"XDG_RUNTIME_DIR": directory}):
                    self.assertTrue(tools.probe_ydotool())
            with patch.dict(tools.os.environ, {"XDG_RUNTIME_DIR": directory}):
                self.assertFalse(tools.probe_ydotool())

    def test_speech_ping_on_unix_socket(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "speech.sock")
            listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            listener.bind(path)
            listener.listen(1)

            def serve():
                conn, _ = listener.accept()
                with conn:
                    self.assertIn(b'"ping"', conn.recv(256))
                    conn.sendall(b'{"status":"ok","ready":true}\n')
                listener.close()

            worker = threading.Thread(target=serve, daemon=True)
            worker.start()
            self.assertTrue(tools.probe_speech(path))
            worker.join(timeout=2)
            self.assertFalse(worker.is_alive())
            self.assertFalse(tools.probe_speech(path))

    def test_custom_socket_expression_does_not_execute(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            config = home / ".config/hermeskey/hermeskey.env"
            config.parent.mkdir(parents=True)
            config.write_text("SOCK=$(touch /tmp/never-do-this)\n")
            with patch.object(tools.Path, "home", return_value=home):
                self.assertIsNone(tools.speech_socket())
            self.assertFalse(Path("/tmp/never-do-this").exists())


if __name__ == "__main__":
    unittest.main()
