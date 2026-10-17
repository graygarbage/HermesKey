"""Validate startup polling and transcript checks without a live model."""
import importlib.util
import io
import tempfile
from contextlib import redirect_stdout
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

MODULE = Path(__file__).resolve().parents[1] / "scripts/verify-install.py"
spec = importlib.util.spec_from_file_location("verify_install", MODULE)
verify_install = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify_install)


class VerifyInstallTests(unittest.TestCase):
    def setUp(self):
        self.sample_dir = tempfile.TemporaryDirectory()
        self.sample = Path(self.sample_dir.name) / "speech.wav"
        self.sample.write_bytes(b"test fixture")
        self.addCleanup(self.sample_dir.cleanup)

    @patch.object(verify_install.subprocess, "run", return_value=Mock(returncode=0))
    @patch.object(verify_install.time, "sleep")
    @patch.object(verify_install, "request")
    def test_waits_and_transcribes(self, request, _sleep, _service):
        request.side_effect = [FileNotFoundError(),
                               {"status": "ok", "ready": True},
                               {"status": "ok", "text": "This is a test of speech recognition."}]
        verify_install.verify("/tmp/example.sock", self.sample, 60, 15)
        self.assertEqual(request.call_args_list[-1].args[1]["wav"], str(self.sample))

    @patch.object(verify_install, "request", side_effect=[{"status": "ok", "ready": True},
                                                          {"status": "error", "error": "decoder failed"}])
    def test_reports_transcription_error(self, _request):
        with self.assertRaisesRegex(RuntimeError, "check local service diagnostics") as result:
            verify_install.verify("/tmp/example.sock", self.sample, 60, 15)
        self.assertNotIn("decoder failed", str(result.exception))

    @patch.object(verify_install, "request", side_effect=[{"status": "ok", "ready": True},
                                                          {"status": "ok", "text": ""}])
    def test_rejects_empty_transcript(self, _request):
        with self.assertRaisesRegex(RuntimeError, "expected words"):
            verify_install.verify("/tmp/example.sock", self.sample, 60, 15)

    def test_custom_sample_text_never_appears_on_success_or_failure(self):
        marker = "PRIVATE_SYNTHETIC_TRANSCRIPT_DO_NOT_PRINT"
        stdout = io.StringIO()
        with patch.object(verify_install.subprocess, "run", return_value=Mock(returncode=0)), \
             patch.object(verify_install, "request", side_effect=[
                 {"status": "ok", "ready": True},
                 {"status": "ok", "text": f"This is a test of speech recognition. {marker}"},
             ]), redirect_stdout(stdout):
            verify_install.verify("/tmp/example.sock", self.sample, 60, 15)
        self.assertIn("Speech smoke test passed.", stdout.getvalue())
        self.assertNotIn(marker, stdout.getvalue())

        stdout = io.StringIO()
        with patch.object(verify_install, "request", side_effect=[
                 {"status": "ok", "ready": True}, {"status": "ok", "text": marker},
             ]), redirect_stdout(stdout), self.assertRaises(RuntimeError) as result:
            verify_install.verify("/tmp/example.sock", self.sample, 60, 15)
        self.assertNotIn(marker, stdout.getvalue() + str(result.exception))

    @patch.object(verify_install.time, "sleep")
    @patch.object(verify_install.time, "monotonic", side_effect=[0, 0, 0, 10, 11])
    @patch.object(verify_install, "request", side_effect=FileNotFoundError())
    def test_readiness_timeout(self, _request, _clock, _sleep):
        with self.assertRaisesRegex(RuntimeError, "timeout"):
            verify_install.verify("/tmp/example.sock", self.sample, 10, 15)


if __name__ == "__main__":
    unittest.main()
