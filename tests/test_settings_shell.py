"""Offscreen settings tests; no microphone is opened or real services restarted."""
import importlib.util
import json
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
        cls.module = module
        cls.parse_sources = staticmethod(module.parse_json_sources)

    def window(self, path):
        with patch.object(self.SettingsWindow, "refresh_sources"):
            return self.SettingsWindow(path)

    def test_default_settings_path_matches_service_with_custom_xdg(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            config = home / ".config/hermeskey/hermeskey.env"
            config.parent.mkdir(parents=True)
            config.write_text("MODEL=medium\nSTT_LANG=en\n")
            with patch.dict(os.environ, {"HOME": str(home), "XDG_CONFIG_HOME": str(Path(directory) / "xdg")}), \
                 patch.object(Path, "home", return_value=home):
                window = self.window(None)
                self.assertEqual(window.path, config)
                self.assertIsNotNone(window.document)
                self.assertNotIn("Custom config overrides", window.notice.text())
                window.model_picker.setCurrentIndex(window.model_picker.findData("tiny"))
                with patch.object(window, "validate"), \
                     patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
                    self.assertTrue(window.save_changes())
                self.assertIn("MODEL=tiny", config.read_text())
                self.assertFalse((Path(directory) / "xdg/hermeskey/hermeskey.env").exists())
                window.close()

    def test_speech_page_clarifies_spoken_language_not_translation(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "hermeskey.env"
            config.write_text("MODEL=medium\nSTT_LANG=en\n")
            window = self.window(config)
            window.resize(680, 420)
            window.show()
            self.app.processEvents()
            self.assertEqual(window.language_label.text(), "Spoken language:")
            self.assertIs(window.language_label.buddy(), window.language_picker)
            self.assertTrue(window.language_hint.isVisible())
            self.assertIn("language you speak", window.language_hint.text())
            self.assertIn("Auto-detect", window.language_hint.text())
            self.assertIn("does not translate", window.language_hint.text())
            self.assertTrue(window.offline_toggle.isVisible())
            hint_bottom = window.language_hint.mapTo(window, window.language_hint.rect().bottomLeft()).y()
            offline_top = window.offline_toggle.mapTo(window, window.offline_toggle.rect().topLeft()).y()
            mic_top = window.source_picker.mapTo(window, window.source_picker.rect().topLeft()).y()
            self.assertLess(hint_bottom, offline_top)
            self.assertLess(offline_top + window.offline_toggle.height(), mic_top)
            self.assertEqual(window.language_picker.currentData(), "en")
            window.close()
            self.assertEqual(config.read_text(), "MODEL=medium\nSTT_LANG=en\n")

    def test_advanced_config_uses_canonical_file_and_refuses_unsaved_edits(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "hermeskey.env"
            config.write_text("MODEL=medium\nSTT_LANG=en\n")
            window = self.window(config)
            window.model_picker.setCurrentIndex(window.model_picker.findData("tiny"))
            with patch.object(self.module.QDesktopServices, "openUrl", return_value=True) as opened, \
                 patch.object(QMessageBox, "information") as info:
                window.system_panel.config_button.click()
                opened.assert_not_called()
                info.assert_called_once()
                window.model_picker.setCurrentIndex(window.model_picker.findData("medium"))
                window.system_panel.config_button.click()
                self.assertEqual(opened.call_args.args[0].toLocalFile(), str(config))
            window.close()

    def test_system_panel_does_not_confuse_active_with_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "hermeskey.env"
            config.write_text("MODEL=medium\nSTT_LANG=en\n")
            window = self.window(config)
            panel = window.system_panel
            states = {"hermeskey.service": {"active": "active", "ready": False},
                      "hermeskey-ydotoold.service": {"active": "active", "ready": True}}
            def fake_process(_slot, _program, _args, finished, timeout=10000):
                finished(True, json.dumps(states))
                return True
            with patch.object(panel, "run_process", side_effect=fake_process):
                panel.refresh()
            self.assertIn("not responding", panel.labels["hermeskey.service"].text())
            self.assertIn("Ready", panel.labels["hermeskey-ydotoold.service"].text())
            window.close()

    def test_restart_uses_fixed_user_systemctl_and_waits_for_readiness(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "hermeskey.env"
            config.write_text("MODEL=medium\nSTT_LANG=en\n")
            window = self.window(config)
            panel = window.system_panel
            with patch.object(panel, "run_process", return_value=True) as run:
                panel.restart_units(("hermeskey.service",))
            self.assertEqual(run.call_args.args[:3], ("action", "systemctl",
                                                      ["--user", "restart", "hermeskey.service"]))
            self.assertIn("Restart requested", panel.labels["hermeskey.service"].text())
            self.assertFalse(panel.speech_button.isEnabled())
            panel.set_actions_enabled(True)
            window.close()

    def test_system_restart_requires_decision_about_unsaved_edits(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "hermeskey.env"
            config.write_text("MODEL=medium\nSTT_LANG=en\n")
            window = self.window(config)
            with patch.object(window.system_panel, "refresh"):
                window.navigation.setCurrentRow(3)
            window.model_picker.setCurrentIndex(window.model_picker.findData("tiny"))
            with patch.object(window.system_panel, "restart_units") as restart, \
                 patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Cancel):
                window.request_service_restart(("hermeskey.service",))
            restart.assert_not_called()
            with patch.object(window.system_panel, "restart_units") as restart, \
                 patch.object(QMessageBox, "question", side_effect=[QMessageBox.StandardButton.No,
                                                                      QMessageBox.StandardButton.Yes]):
                window.request_service_restart(("hermeskey.service",))
            restart.assert_called_once_with(("hermeskey.service",))
            self.assertEqual(window.model_picker.currentData(), "medium")
            self.assertEqual(config.read_text(), "MODEL=medium\nSTT_LANG=en\n")
            window.close()

    def test_system_restart_can_save_first_without_automatic_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "hermeskey.env"
            config.write_text("MODEL=medium\nSTT_LANG=en\n")
            window = self.window(config)
            window.model_picker.setCurrentIndex(window.model_picker.findData("tiny"))
            with patch.object(window, "validate"), patch.object(window.system_panel, "restart_units") as restart, \
                 patch.object(QMessageBox, "question", side_effect=[QMessageBox.StandardButton.Yes,
                                                                      QMessageBox.StandardButton.Yes]):
                window.request_service_restart(("hermeskey.service",))
            restart.assert_called_once_with(("hermeskey.service",))
            self.assertIn("MODEL=tiny", config.read_text())
            window.close()

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
            window.model_picker.setCurrentIndex(window.model_picker.findData("small"))
            with patch.object(window, "validate"), patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
                window.apply_button.click()
            self.assertTrue(window.isVisible())
            self.assertIn("MODEL=small", config.read_text())
            self.assertIn("# preserved\n", config.read_text())
            self.assertFalse(window.apply_button.isEnabled())
            window.language_picker.setCurrentIndex(window.language_picker.findData(""))
            window.buttons.button(QDialogButtonBox.StandardButton.Cancel).click()
            self.assertFalse(window.isVisible())
            self.assertIn("STT_LANG=en", config.read_text())

    def test_custom_model_and_language_values_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "hermeskey.env"
            config.write_text("MODEL=owner/custom-whisper\nSTT_LANG=nl\n")
            window = self.window(config)
            self.assertEqual(window.model_picker.currentData(), "custom:")
            self.assertEqual(window.model_edit.text(), "owner/custom-whisper")
            self.assertEqual(window.language_picker.currentData(), "custom:")
            self.assertEqual(window.language_edit.text(), "nl")
            self.assertFalse(window.apply_button.isEnabled())
            window.buttons.button(QDialogButtonBox.StandardButton.Cancel).click()
            self.assertEqual(config.read_text(), "MODEL=owner/custom-whisper\nSTT_LANG=nl\n")

    def test_custom_model_and_auto_language_save_without_downloading(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "hermeskey.env"
            config.write_text("MODEL=medium\nSTT_LANG=en\n")
            window = self.window(config)
            window.model_picker.setCurrentIndex(window.model_picker.findData("custom:"))
            window.model_edit.setText("owner/custom-whisper")
            window.language_picker.setCurrentIndex(window.language_picker.findData(""))
            with patch.object(window, "validate"), patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No), \
                 patch("subprocess.run") as run:
                self.assertTrue(window.save_changes())
            run.assert_not_called()
            self.assertIn("MODEL=owner/custom-whisper", config.read_text())
            self.assertIn("STT_LANG=\n", config.read_text())
            window.close()

    def test_offline_speech_toggle_saves_only_with_restart_consent(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "hermeskey.env"
            config.write_text("MODEL=medium\nSTT_LANG=en\n")
            window = self.window(config)
            window.show()
            self.app.processEvents()
            self.assertTrue(window.offline_toggle.isVisible())
            self.assertFalse(window.offline_toggle.isChecked())
            window.offline_toggle.setChecked(True)
            with patch.object(window, "validate"), \
                 patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No) as question, \
                 patch("subprocess.run") as run:
                self.assertTrue(window.save_changes())
            question.assert_called_once()
            run.assert_not_called()
            self.assertIn("HERMESKEY_OFFLINE=1\n", config.read_text())
            self.assertTrue(window.offline_toggle.isChecked())
            self.assertIn("Restart", window.notice.text())
            window.offline_toggle.setChecked(False)
            window.revert_unsaved()
            self.assertTrue(window.offline_toggle.isChecked())
            window.close()

    def test_privacy_first_typing_explicitly_disables_new_backups(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "hermeskey.env"
            config.write_text("MODEL=medium\nSTT_LANG=en\nINSERT_MODE=clipboard\nCOPY_TO_CLIPBOARD=1\n")
            window = self.window(config)
            window.resize(680, 420)
            window.show()
            window.navigation.setCurrentRow(1)
            self.app.processEvents()
            self.assertTrue(window.privacy_button.isVisible())
            self.assertIn("KDE clipboard history", window.clipboard_hint.text())
            self.assertTrue(window.privacy_button.isEnabled())
            self.assertFalse(window.clipboard_backup.isEnabled())
            window.privacy_button.click()
            self.assertEqual(window.insert_picker.currentData(), "type")
            self.assertFalse(window.clipboard_backup.isChecked())
            self.assertTrue(window.clipboard_backup.isEnabled())
            self.assertIn("existing clipboard history is unchanged", window.notice.text())
            self.app.processEvents()
            hint_bottom = window.clipboard_hint.mapTo(window, window.clipboard_hint.rect().bottomLeft()).y()
            notice_top = window.notice.mapTo(window, window.notice.rect().topLeft()).y()
            self.assertLess(hint_bottom, notice_top)
            with patch.object(window, "validate"), patch("subprocess.run") as run, \
                 patch.object(QMessageBox, "question") as question:
                self.assertTrue(window.save_changes())
            run.assert_not_called()
            question.assert_not_called()
            self.assertIn("INSERT_MODE=type", config.read_text())
            self.assertIn("COPY_TO_CLIPBOARD=0", config.read_text())
            self.assertFalse(window.privacy_button.isEnabled())
            window.close()

    def test_behavior_only_save_does_not_restart_or_change_clipboard_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "hermeskey.env"
            config.write_text("MODEL=medium\nSTT_LANG=en\nCOPY_TO_CLIPBOARD=0\n")
            window = self.window(config)
            self.assertFalse(window.clipboard_backup.isChecked())
            window.insert_picker.setCurrentIndex(window.insert_picker.findData("clipboard"))
            self.assertFalse(window.clipboard_backup.isEnabled())
            self.assertFalse(window.clipboard_backup.isChecked())
            window.overlay_toggle.setChecked(False)
            window.sound_toggle.setChecked(False)
            window.focus_safe.setChecked(True)
            with patch.object(window, "validate"), patch.object(QMessageBox, "question") as question:
                self.assertTrue(window.save_changes())
            question.assert_not_called()
            saved = config.read_text()
            for line in ("INSERT_MODE=clipboard", "COPY_TO_CLIPBOARD=0", "OVERLAY_ENABLED=0",
                         "SOUND_ENABLED=0", "FOCUS_SAFE_MODE=1", "MODEL=medium"):
                self.assertIn(line, saved)
            self.assertFalse(window.apply_button.isEnabled())
            window.close()

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
            window.language_picker.setCurrentIndex(window.language_picker.findData("custom:"))
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
            window.model_picker.setCurrentIndex(window.model_picker.findData("tiny"))
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
