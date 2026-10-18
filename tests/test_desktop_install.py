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
        systemctl.write_text('#!/usr/bin/env sh\nprintf "%s\\n" "$*" >> "$TEST_SYSTEMCTL_LOG"\nexit 0\n')
        systemctl.chmod(0o755)
        xdg_open = mockbin / "xdg-open"
        xdg_open.write_text("#!/usr/bin/env sh\nexit 0\n")
        xdg_open.chmod(0o755)
        self.env = dict(os.environ, HOME=str(self.home),
                        XDG_CONFIG_HOME=str(self.home / ".config"),
                        XDG_DATA_HOME=str(self.home / ".local/share"),
                        TEST_SYSTEMCTL_LOG=str(Path(self.temp.name) / "systemctl-calls"),
                        XDG_RUNTIME_DIR=str(Path(self.temp.name) / "runtime"),
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

    def test_custom_xdg_fresh_install_uses_single_service_config(self):
        custom_xdg = Path(self.temp.name) / "private-xdg"
        self.env["XDG_CONFIG_HOME"] = str(custom_xdg)
        self.install()
        canonical = self.home / ".config/hermeskey/hermeskey.env"
        self.assertTrue(canonical.is_file())
        self.assertFalse((custom_xdg / "hermeskey/hermeskey.env").exists())
        self.assertEqual(canonical.stat().st_mode & 0o777, 0o600)
        self.assertEqual(canonical.parent.stat().st_mode & 0o777, 0o700)
        venv_python = Path(self.temp.name) / "custom-venv/bin/python"
        venv_python.parent.mkdir(parents=True)
        venv_python.write_text("#!/usr/bin/env sh\nexit 0\n")
        venv_python.chmod(0o755)
        canonical.write_text(f'MODEL=tiny\nSTT_LANG=fr\nPYTHON_STT="{venv_python}"\n')
        subprocess.run(["bash", str(ROOT / "scripts/check-config.sh"), str(venv_python.parent.parent)],
                       env=self.env, capture_output=True, check=True)
        for unit in ("hermeskey.service", "hermeskey-ydotoold.service"):
            text = (self.home / ".config/systemd/user" / unit).read_text()
            self.assertIn("EnvironmentFile=-%h/.config/hermeskey/hermeskey.env", text)
        hotkey = subprocess.run([str(self.home / ".local/bin/hermeskey"), "--status"],
                                env=self.env, capture_output=True, text=True, check=True)
        self.assertIn(str(canonical), hotkey.stdout)
        self.assertIn("model:     tiny", hotkey.stdout)
        self.assertIn("language:  fr", hotkey.stdout)
        doctor = subprocess.run([str(self.home / ".local/bin/hermeskey-doctor"), "--config-only"],
                                env=self.env, capture_output=True, text=True)
        self.assertIn("Config file present", doctor.stdout)
        subprocess.run([str(self.home / ".local/bin/hermeskey-open-config")],
                       env=self.env, capture_output=True, check=True)
        self.assertFalse((custom_xdg / "hermeskey/hermeskey.env").exists())

    def test_custom_xdg_upgrade_copies_legacy_once_without_executing_it(self):
        custom_xdg = Path(self.temp.name) / "private-xdg"
        self.env["XDG_CONFIG_HOME"] = str(custom_xdg)
        legacy = custom_xdg / "hermeskey/hermeskey.env"
        legacy.parent.mkdir(parents=True)
        legacy.parent.chmod(0o755)
        marker = Path(self.temp.name) / "never-executed"
        content = f'MODEL=tiny\nSTT_LANG=fr\nPYTHON_STT="{self.temp.name}/venv/bin/python"\nUNRELATED=$(touch "{marker}")\n'
        legacy.write_text(content)
        legacy.chmod(0o644)
        venv = Path(self.temp.name) / "venv/bin/python"
        venv.parent.mkdir(parents=True)
        venv.write_text("#!/usr/bin/env sh\nexit 0\n")
        venv.chmod(0o755)
        subprocess.run(["bash", str(ROOT / "scripts/check-config.sh"), str(venv.parent.parent)],
                       env=self.env, capture_output=True, check=True)
        self.assertFalse(marker.exists())
        self.install()
        canonical = self.home / ".config/hermeskey/hermeskey.env"
        self.assertEqual(canonical.read_text(), content)
        archive = legacy.with_name("hermeskey.env.pre-hermeskey-xdg-migration")
        self.assertFalse(legacy.exists())
        self.assertEqual(archive.read_text(), content)
        self.assertEqual(archive.stat().st_mode & 0o777, 0o600)
        self.assertFalse(marker.exists())
        self.assertEqual(canonical.stat().st_mode & 0o777, 0o600)
        self.assertEqual(canonical.parent.stat().st_mode & 0o777, 0o700)
        canonical.write_text(content + "# future changes\n")
        self.install()  # no stale XDG file conflicts with future GUI edits
        self.assertEqual(canonical.read_text(), content + "# future changes\n")
        self.assertEqual(archive.read_text(), content)

    def test_custom_xdg_conflict_fails_before_install_or_service_restart(self):
        custom_xdg = Path(self.temp.name) / "private-xdg"
        self.env["XDG_CONFIG_HOME"] = str(custom_xdg)
        canonical = self.home / ".config/hermeskey/hermeskey.env"
        legacy = custom_xdg / "hermeskey/hermeskey.env"
        canonical.parent.mkdir(parents=True)
        legacy.parent.mkdir(parents=True)
        canonical.write_text("MODEL=tiny\n")
        legacy.write_text("MODEL=medium\n")
        result = subprocess.run(["bash", str(ROOT / "install.sh")], env=self.env,
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Conflicting canonical and custom-XDG", result.stderr)
        self.assertEqual(canonical.read_text(), "MODEL=tiny\n")
        self.assertEqual(legacy.read_text(), "MODEL=medium\n")
        self.assertFalse((self.home / ".local/bin/hermeskey").exists())
        self.assertFalse(Path(self.env["TEST_SYSTEMCTL_LOG"]).exists())

    def test_xdg_alias_of_canonical_path_does_not_archive_active_config(self):
        canonical = self.home / ".config/hermeskey/hermeskey.env"
        canonical.parent.mkdir(parents=True)
        canonical.write_text("MODEL=tiny\n")
        self.env["XDG_CONFIG_HOME"] = f"{self.home}/.config/."
        self.install()
        self.assertEqual(canonical.read_text(), "MODEL=tiny\n")
        self.assertFalse(canonical.with_name("hermeskey.env.pre-hermeskey-xdg-migration").exists())

    def test_custom_xdg_migration_refuses_existing_backup_and_symlink(self):
        custom_xdg = Path(self.temp.name) / "private-xdg"
        self.env["XDG_CONFIG_HOME"] = str(custom_xdg)
        legacy = custom_xdg / "hermeskey/hermeskey.env"
        legacy.parent.mkdir(parents=True)
        legacy.write_text("MODEL=tiny\n")
        archive = legacy.with_name("hermeskey.env.pre-hermeskey-xdg-migration")
        archive.write_text("preserve this backup\n")
        for unsafe in (False, True):
            if unsafe:
                archive.unlink()
                legacy.unlink()
                legacy.symlink_to(archive)
            result = subprocess.run(["bash", str(ROOT / "install.sh")], env=self.env,
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((self.home / ".local/bin/hermeskey").exists())
            self.assertFalse(Path(self.env["TEST_SYSTEMCTL_LOG"]).exists())
            if not unsafe:
                self.assertEqual(archive.read_text(), "preserve this backup\n")
        self.assertFalse(archive.exists())

    def test_upgrade_refuses_active_dictation_before_changing_files(self):
        self.install()
        calls = Path(self.env["TEST_SYSTEMCTL_LOG"])
        previous_calls = calls.read_text()
        installed = self.home / ".local/bin/hermeskey"
        previous_binary = installed.read_bytes()
        runtime = Path(self.env["XDG_RUNTIME_DIR"])
        runtime.mkdir()
        (runtime / "hermeskey_recording.pid").write_text("synthetic-state")
        result = subprocess.run(["bash", str(ROOT / "install.sh")], env=self.env,
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Finish dictation", result.stderr)
        self.assertEqual(installed.read_bytes(), previous_binary)
        self.assertEqual(calls.read_text(), previous_calls)

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
