"""Offscreen tests for the settings shell; no config or services are touched."""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtWidgets import QApplication, QDialogButtonBox
except ImportError:
    QApplication = None


@unittest.skipUnless(QApplication is not None, "system PySide6 is not available")
class SettingsShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        module_path = Path(__file__).resolve().parents[1] / "bin/hermeskey-settings.py"
        spec = importlib.util.spec_from_file_location("hermeskey_settings", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.SettingsWindow = module.SettingsWindow

    def test_navigation_and_no_false_save(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "hermeskey.env"
            config.write_text("MODEL=medium\n")
            window = self.SettingsWindow()
            window.show()
            self.app.processEvents()
            self.assertTrue(window.isVisible())
            self.assertEqual(window.navigation.count(), 4)
            self.assertEqual(window.pages.currentIndex(), 0)
            window.navigation.setCurrentRow(2)
            self.assertEqual(window.pages.currentIndex(), 2)
            self.assertFalse(window.save_button.isEnabled())
            self.assertFalse(window.apply_button.isEnabled())
            window.buttons.button(QDialogButtonBox.StandardButton.Cancel).click()
            self.assertTrue(window.isHidden())
            self.assertEqual(config.read_text(), "MODEL=medium\n")


if __name__ == "__main__":
    unittest.main()
