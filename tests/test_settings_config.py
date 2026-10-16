"""Settings file round-trips must not execute or overwrite unrelated config."""
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
from hermeskey_settings_config import ConfigChanged, ConfigDocument, ConfigError


class SettingsConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "hermeskey.env"
        self.text = (
            "# custom settings\nMODEL='medium'  # current model\n"
            "STT_LANG=en\nPASTE_FOR_APPS=$TERMINAL_APPS\n"
            "# a shell expression we never evaluate\nUNKNOWN=$(touch /tmp/should-not-run)\n"
        )
        self.path.write_text(self.text)

    def test_change_only_requested_keys_preserving_all_else(self):
        doc = ConfigDocument(self.path)
        self.assertEqual(doc.values, {"MODEL": "medium", "STT_LANG": "en"})
        doc.save({"MODEL": "small.en", "STT_LANG": ""}, lambda candidate: None)
        self.assertEqual(self.path.read_text(), self.text.replace("MODEL='medium'", "MODEL=small.en").replace("STT_LANG=en", "STT_LANG="))
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        self.assertEqual(doc.values["MODEL"], "small.en")
        self.assertFalse(list(self.path.parent.glob(".hermeskey-env-*")))

    def test_validator_failure_leaves_file_unchanged(self):
        def reject(_candidate):
            raise ConfigError("invalid code")
        with self.assertRaisesRegex(ConfigError, "invalid code"):
            ConfigDocument(self.path).save({"STT_LANG": "zz"}, reject)
        self.assertEqual(self.path.read_text(), self.text)
        self.assertFalse(list(self.path.parent.glob(".hermeskey-env-*")))

    def test_external_edits_are_not_lost(self):
        doc = ConfigDocument(self.path)
        self.path.write_text(self.text + "# external editor\n")
        with self.assertRaises(ConfigChanged):
            doc.save({"MODEL": "tiny"}, lambda candidate: None)
        self.assertIn("external editor", self.path.read_text())

    def test_refuses_duplicate_or_unsupported_assignments(self):
        for value in ("MODEL=medium\nMODEL=small\n", "MODEL=$DYNAMIC_MODEL\n", "export STT_LANG=en\n"):
            with self.subTest(value=value):
                self.path.write_text(value)
                with self.assertRaises(ConfigError):
                    ConfigDocument(self.path)

    def test_refuses_shell_metacharacters_and_symlinks(self):
        doc = ConfigDocument(self.path)
        for value in ("$(touch /tmp/a)", "owner/name with spaces", "x\nKEEP_AUDIO=1"):
            with self.subTest(value=value), self.assertRaises(ConfigError):
                doc.render({"MODEL": value})
        link = self.path.parent / "link.env"
        link.symlink_to(self.path)
        with self.assertRaises(ConfigError):
            ConfigDocument(link)

    def test_appends_missing_key_without_touching_unknown_lines(self):
        self.path.write_text("# personal\nUNKNOWN=ok")
        ConfigDocument(self.path).save({"MODEL": "base"}, lambda candidate: None)
        self.assertEqual(self.path.read_text(), "# personal\nUNKNOWN=ok\nMODEL=base\n")


if __name__ == "__main__":
    unittest.main()
