"""Error diagnostics must never disclose user-supplied request or exception data."""
import importlib.util
import json
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

    def test_model_load_does_not_log_custom_path(self):
        secret = "PRIVATE_MODEL_FOLDER"
        self.server.model_name = f"/home/user/{secret}"
        with patch.object(server_module, "WhisperModel", return_value=Mock()), \
             patch.object(server_module.logger, "info") as info:
            self.server.load()
        self.assertNotIn(secret, str(info.call_args_list))

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
