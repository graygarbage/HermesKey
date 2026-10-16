"""Offscreen tests for the settings window, without user services or config."""
import importlib.util
import os
import sys
import tempfile
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

    def test_navigation_apply_save_and_cancel(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "hermeskey.env"
            config.write_text("# preserved\nMODEL=medium\nSTT_LANG=en\nUNKNOWN=value\n")
            window = self.SettingsWindow(config)
            window.show()
            self.app.processEvents()
            self.assertTrue(window.isVisible())
            self.assertEqual(window.navigation.count(), 4)
            self.assertEqual(window.pages.currentIndex(), 0)
            self.assertEqual(window.model_edit.text(), "medium")
            window.navigation.setCurrentRow(2)
            self.assertEqual(window.pages.currentIndex(), 2)
            self.assertFalse(window.save_button.isEnabled())
            window.model_edit.setText("small")
            self.assertTrue(window.apply_button.isEnabled())
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
            window = self.SettingsWindow(config)
            window.language_edit.setText("xyz")
            with patch.object(QMessageBox, "warning") as warning:
                self.assertFalse(window.save_changes())
            warning.assert_called_once()
            self.assertEqual(config.read_text(), "MODEL=medium\nSTT_LANG=en\n")

    def test_save_closes_and_discard_prompt_on_window_close(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "hermeskey.env"
            config.write_text("MODEL=medium\nSTT_LANG=en\n")
            window = self.SettingsWindow(config)
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
