"""Error diagnostics must never disclose user-supplied request or exception data."""
import importlib.util
import io
import json
import logging
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

MODULE = Path(__file__).resolve().parents[1] / "bin/hermeskey-server.py"
spec = importlib.util.spec_from_file_location("hermeskey_server", MODULE)
with patch.dict(sys.modules, {"faster_whisper": types.SimpleNamespace(WhisperModel=Mock())}):
    server_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(server_module)


class ServerLoggingTests(unittest.TestCase):
    def setUp(self):
        self.server = server_module.Server("/tmp/not-used.sock", "medium", "en")

    def test_exception_never_leaks_into_log_or_response(self):
        secret = "PRIVATE_AUDIO_PATH_AND_TRANSCRIPT"
        with tempfile.TemporaryDirectory() as directory:
            wav = Path(directory) / f"{secret}.wav"
            wav.write_bytes(b"fake wav")
            self.server.model = Mock()
            self.server.model.transcribe.side_effect = RuntimeError(secret)
            with patch.object(server_module.logger, "error") as error:
                reply = self.server.process(json.dumps({"cmd": "transcribe", "wav": str(wav)}).encode())
            self.assertEqual(reply["status"], "error")
            self.assertNotIn(secret, str(reply))
            self.assertNotIn(secret, str(error.call_args))
            self.assertIn("RuntimeError", str(error.call_args))
            self.assertIn("handle", str(error.call_args))

    def test_invalid_json_does_not_log_request_body(self):
        secret = "PRIVATE_REQUEST_TEXT"
        with patch.object(server_module.logger, "error") as error:
            reply = self.server.process(f'{{"cmd":"{secret}"'.encode())
        self.assertNotIn(secret, str(reply) + str(error.call_args))
        self.assertIn("JSONDecodeError", str(error.call_args))

    def test_missing_audio_path_not_echoed(self):
        secret = "PRIVATE_FILENAME"
        reply = self.server.process(json.dumps({"cmd": "transcribe", "wav": f"/tmp/{secret}.wav"}).encode())
        self.assertEqual(reply, {"status": "error", "error": "wav not found"})
        self.assertNotIn(secret, str(reply))

    def test_failure_formatter_omits_exception_message(self):
        secret = "PRIVATE_EXCEPTION_DETAIL"
        try:
            raise OSError(secret)
        except OSError as exc:
            with patch.object(server_module.logger, "error") as error:
                server_module.log_failure("startup", exc)
        self.assertNotIn(secret, str(error.call_args))
        self.assertIn("OSError", str(error.call_args))

    def test_third_party_request_logs_are_not_forwarded(self):
        handler = server_module.logger.handlers[0]
        original = handler.stream
        output = io.StringIO()
        try:
            handler.setStream(output)
            logging.getLogger("httpx").warning("PRIVATE_SYNTHETIC_HTTP_REQUEST_URL")
            logging.getLogger("faster_whisper").warning("PRIVATE_SYNTHETIC_MODEL_PATH")
            server_module.log("loading speech model")
        finally:
            handler.setStream(original)
        self.assertIn("loading speech model", output.getvalue())
        self.assertNotIn("PRIVATE_SYNTHETIC", output.getvalue())
        self.assertIsInstance(logging.getLogger().handlers[0], logging.NullHandler)

    def test_model_load_does_not_log_custom_path(self):
        secret = "PRIVATE_MODEL_FOLDER"
        self.server.model_name = f"/home/user/{secret}"
        with patch.object(server_module, "WhisperModel", return_value=Mock()), \
             patch.object(server_module.logger, "info") as info:
            self.server.load()
        self.assertNotIn(secret, str(info.call_args_list))

    def test_service_uses_environment_without_private_model_in_argv(self):
        secret = "PRIVATE_SYNTHETIC_MODEL_PATH"
        unit = MODULE.parents[1] / "systemd/user/hermeskey.service"
        text = unit.read_text()
        self.assertIn("EnvironmentFile=", text)
        self.assertIn("exec ", text)
        self.assertNotIn("--model", text)
        self.assertNotIn("--lang", text)
        self.assertNotIn("--socket", text)
        with patch.dict(os.environ, {"SOCK": "/tmp/private-test.sock", "MODEL": secret, "STT_LANG": ""}), \
             patch.object(server_module, "Server") as server, \
             patch.object(server_module.signal, "signal"), \
             patch.object(sys, "argv", ["hermeskey-server.py"]):
            self.assertEqual(server_module.main(), 0)
        server.assert_called_once_with("/tmp/private-test.sock", secret, "")

    def test_startup_failure_has_no_raw_traceback(self):
        secret = "PRIVATE_STARTUP_ERROR"
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(server_module, "WhisperModel", side_effect=RuntimeError(secret)), \
             patch.object(server_module.signal, "signal"), \
             patch.object(server_module.logger, "error") as error, \
             patch.object(sys, "argv", ["hermeskey-server.py", "--socket", f"{directory}/speech.sock"]):
            result = server_module.main()
        self.assertEqual(result, 1)
        self.assertNotIn(secret, str(error.call_args_list))


if __name__ == "__main__":
    unittest.main()
