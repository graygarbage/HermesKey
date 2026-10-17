"""A fresh install and an upgrade expose one app-menu entry, preserving IDs."""
import configparser
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ("status", "doctor", "config", "logs", "control-center")


class DesktopInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "home"
        mockbin = Path(self.temp.name) / "mockbin"
        mockbin.mkdir()
        systemctl = mockbin / "systemctl"
        systemctl.write_text("#!/usr/bin/env sh\nexit 0\n")
        systemctl.chmod(0o755)
        xdg_open = mockbin / "xdg-open"
        xdg_open.write_text("#!/usr/bin/env sh\nexit 0\n")
        xdg_open.chmod(0o755)
        self.env = dict(os.environ, HOME=str(self.home),
                        XDG_CONFIG_HOME=str(self.home / ".config"),
                        XDG_DATA_HOME=str(self.home / ".local/share"),
                        PATH=f"{mockbin}:{os.environ['PATH']}")
        self.apps = self.home / ".local/share/applications"

    def install(self):
        subprocess.run(["bash", str(ROOT / "install.sh")], env=self.env, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def desktop(self, name):
        path = self.apps / f"hermeskey-{name}.desktop"
        cfg = configparser.ConfigParser(interpolation=None)
        cfg.read(path)
        return path, cfg["Desktop Entry"]

    def assert_single_visible_launcher(self):
        entries = sorted(self.apps.glob("hermeskey-*.desktop"))
        self.assertEqual(len(entries), 6)
        for name in (*LEGACY, "settings"):
            path, entry = self.desktop(name)
            self.assertEqual(entry.get("NoDisplay", "false").lower() == "true", name != "settings")
            self.assertTrue(Path(entry["Exec"]).exists())
            if shutil.which("desktop-file-validate"):
                subprocess.run(["desktop-file-validate", str(path)], check=True,
                               capture_output=True)
        appstream = (self.home / ".local/share/metainfo/hermeskey.metainfo.xml").read_text()
        self.assertIn("<launchable type=\"desktop-id\">hermeskey-settings.desktop</launchable>", appstream)

    def test_config_opener_creates_private_file_and_tightens_existing_one(self):
        self.home.mkdir()
        helper = ROOT / "bin/hermeskey-open-config"
        subprocess.run(["bash", str(helper)], env=self.env, check=True, capture_output=True)
        config = self.home / ".config/hermeskey/hermeskey.env"
        self.assertEqual(config.stat().st_mode & 0o777, 0o600)
        self.assertEqual(config.parent.stat().st_mode & 0o777, 0o700)
        config.write_text("MODEL=medium\n")
        config.chmod(0o644)
        subprocess.run(["bash", str(helper)], env=self.env, check=True, capture_output=True)
        self.assertEqual(config.stat().st_mode & 0o777, 0o600)
        self.assertEqual(config.read_text(), "MODEL=medium\n")

    def test_symlinked_config_is_rejected_without_changing_target(self):
        directory = self.home / ".config/hermeskey"
        directory.mkdir(parents=True)
        target = Path(self.temp.name) / "external.env"
        target.write_text("MODEL=medium\n")
        target.chmod(0o644)
        (directory / "hermeskey.env").symlink_to(target)
        for command in (["bash", str(ROOT / "install.sh")],
                        ["bash", str(ROOT / "bin/hermeskey-open-config")]):
            result = subprocess.run(command, env=self.env, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
        self.assertEqual(target.read_text(), "MODEL=medium\n")
        self.assertEqual(target.stat().st_mode & 0o777, 0o644)
        self.assertFalse((self.home / ".local/bin/hermeskey").exists())

    def test_fresh_install_and_upgrade_hide_legacy_entries(self):
        self.install()
        self.assert_single_visible_launcher()
        config = self.home / ".config/hermeskey/hermeskey.env"
        self.assertEqual(config.stat().st_mode & 0o777, 0o600)
        self.assertEqual(config.parent.stat().st_mode & 0o777, 0o700)
        config.write_text("MODEL=tiny\nSTT_LANG=en\n")
        config.chmod(0o644)  # older, less-private install
        config.parent.chmod(0o755)
        for name in LEGACY:
            path, _ = self.desktop(name)
            path.write_text("[Desktop Entry]\nName=Old Visible HermesKey\n")
        self.install()  # upgrade from visible legacy launchers
        self.assert_single_visible_launcher()
        self.assertEqual(config.read_text(), "MODEL=tiny\nSTT_LANG=en\n")
        self.assertEqual(config.stat().st_mode & 0o777, 0o600)
        self.assertEqual(config.parent.stat().st_mode & 0o777, 0o700)
        control = (self.home / ".local/bin/hermeskey-control-center").read_text()
        self.assertIn("hermeskey-settings.py", control)
        subprocess.run(["bash", str(ROOT / "uninstall.sh")], env=self.env, check=True,
                       capture_output=True)
        self.assertEqual(list(self.apps.glob("hermeskey-*.desktop")), [])


if __name__ == "__main__":
    unittest.main()
