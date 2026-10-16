"""Offscreen settings tests; no microphone is opened or real services restarted."""
import importlib.util
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtWidgets import QApplication, QDialogButtonBox, QMessageBox
except ImportError:
    QApplication = None


@unittest.skipUnless(QApplication is not None, "system PySide6 is not available")
class SettingsShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        bin_dir = Path(__file__).resolve().parents[1] / "bin"
        sys.path.insert(0, str(bin_dir))
        spec = importlib.util.spec_from_file_location("hermeskey_settings", bin_dir / "hermeskey-settings.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.SettingsWindow = module.SettingsWindow
        cls.parse_sources = staticmethod(module.parse_json_sources)

    def window(self, path):
        with patch.object(self.SettingsWindow, "refresh_sources"):
            return self.SettingsWindow(path)

    def test_navigation_apply_save_and_cancel(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "hermeskey.env"
            config.write_text("# preserved\nMODEL=medium\nSTT_LANG=en\nUNKNOWN=value\n")
            window = self.window(config)
            window.show()
            self.app.processEvents()
            self.assertTrue(window.isVisible())
            self.assertEqual(window.navigation.count(), 4)
            self.assertEqual(window.pages.currentIndex(), 0)
            window.navigation.setCurrentRow(2)
            self.assertEqual(window.pages.currentIndex(), 2)
            self.assertFalse(window.save_button.isEnabled())
            window.model_edit.setText("small")
            with patch.object(window, "validate"), patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
                window.apply_button.click()
            self.assertTrue(window.isVisible())
            self.assertIn("MODEL=small", config.read_text())
            self.assertIn("# preserved\n", config.read_text())
            self.assertFalse(window.apply_button.isEnabled())
            window.language_edit.setText("")
            window.buttons.button(QDialogButtonBox.StandardButton.Cancel).click()
            self.assertFalse(window.isVisible())
            self.assertIn("STT_LANG=en", config.read_text())

    def test_microphone_picker_preserves_missing_device_and_no_model_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "hermeskey.env"
            config.write_text("MODEL=medium\nSTT_LANG=en\nRECORD_SOURCE=alsa_input.unplugged\n")
            window = self.window(config)
            self.assertEqual(window.source_picker.currentData(), "alsa_input.unplugged")
            self.assertIn("Unavailable", window.source_picker.currentText())
            window.sources = self.parse_sources('[{"name":"alsa_input.usb-Mic-00","description":"USB Mic"},'
                                                '{"name":"alsa_input.usb-Mic-01","description":"USB Mic"},'
                                                '{"name":"alsa_output.monitor","description":"Speaker monitor"}]')
            window.populate_sources()
            self.assertEqual(window.source_picker.findData("alsa_output.monitor"), -1)
            self.assertIn("alsa_input.usb-Mic-00", window.source_picker.itemText(
                window.source_picker.findData("alsa_input.usb-Mic-00")))
            window.monitor_toggle.setChecked(True)
            self.assertNotEqual(window.source_picker.findData("alsa_output.monitor"), -1)
            window.source_picker.setCurrentIndex(window.source_picker.findData("alsa_input.usb-Mic-00"))
            with patch.object(window, "validate"), patch.object(QMessageBox, "question") as question:
                self.assertTrue(window.save_changes())
            question.assert_not_called()
            self.assertIn("RECORD_SOURCE=alsa_input.usb-Mic-00", config.read_text())
            window.close()

    def test_async_refresh_falls_back_to_short_listing(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "hermeskey.env"
            config.write_text("MODEL=medium\nSTT_LANG=en\nRECORD_SOURCE=default\n")
            pactl = Path(directory) / "pactl"
            pactl.write_text('#!/bin/sh\nif [ "$1" = "-f" ]; then exit 1; fi\nprintf "42\\talsa_input.fake-mic\\tPipeWire\\tRUNNING\\n"\n')
            pactl.chmod(0o755)
            with patch.dict(os.environ, {"PATH": f"{directory}:{os.environ['PATH']}"}):
                window = self.SettingsWindow(config)
                deadline = time.monotonic() + 3
                while window.source_process is not None and time.monotonic() < deadline:
                    self.app.processEvents()
                    time.sleep(0.01)
                self.assertIsNone(window.source_process)
                self.assertNotEqual(window.source_picker.findData("alsa_input.fake-mic"), -1)
                window.close()

    def test_failed_refresh_keeps_saved_source(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "hermeskey.env"
            config.write_text("MODEL=medium\nSTT_LANG=en\nRECORD_SOURCE=alsa_input.disconnected\n")
            pactl = Path(directory) / "pactl"
            pactl.write_text("#!/bin/sh\nexit 1\n")
            pactl.chmod(0o755)
            with patch.dict(os.environ, {"PATH": f"{directory}:{os.environ['PATH']}"}):
                window = self.SettingsWindow(config)
                deadline = time.monotonic() + 3
                while window.source_process is not None and time.monotonic() < deadline:
                    self.app.processEvents()
                    time.sleep(0.01)
                self.assertIsNone(window.source_process)
                self.assertEqual(window.source_picker.currentData(), "alsa_input.disconnected")
                self.assertFalse(window.apply_button.isEnabled())
                self.assertIn("Cannot refresh", window.source_status.text())
                window.close()

    def test_validation_does_not_execute_unmanaged_shell_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "hermeskey.env"
            marker = Path(directory) / "must-not-exist"
            config.write_text(f"MODEL=medium\nSTT_LANG=en\nUNKNOWN=$(touch {marker})\n")
            self.SettingsWindow.validate(config)
            self.assertFalse(marker.exists())

    def test_invalid_language_is_not_written(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "hermeskey.env"
            config.write_text("MODEL=medium\nSTT_LANG=en\n")
            window = self.window(config)
            window.language_edit.setText("xyz")
            with patch.object(QMessageBox, "warning") as warning:
                self.assertFalse(window.save_changes())
            warning.assert_called_once()
            self.assertEqual(config.read_text(), "MODEL=medium\nSTT_LANG=en\n")

    def test_save_closes_and_discard_prompt_on_window_close(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "hermeskey.env"
            config.write_text("MODEL=medium\nSTT_LANG=en\n")
            window = self.window(config)
            window.show()
            window.model_edit.setText("tiny")
            with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
                window.close()
            self.assertTrue(window.isVisible())
            self.assertIn("MODEL=medium", config.read_text())
            with patch.object(window, "validate"), patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
                window.save_button.click()
            self.assertFalse(window.isVisible())
            self.assertIn("MODEL=tiny", config.read_text())


if __name__ == "__main__":
    unittest.main()
