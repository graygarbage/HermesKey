"""Bootstrap must never silently float speech dependencies or build source distributions."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DependencyLockTests(unittest.TestCase):
    def test_every_reviewed_requirement_has_an_exact_version(self):
        requirements = (ROOT / "requirements.txt").read_text().splitlines()
        pins = {}
        for line in requirements:
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([0-9]+(?:\.[0-9]+)+(?:[A-Za-z0-9.-]*)?)", line)
            self.assertIsNotNone(match, f"Nonliteral/unpinned dependency: {line}")
            name = re.sub(r"[-_.]+", "-", match.group(1)).lower()
            self.assertNotIn(name, pins)
            pins[name] = match.group(2)
        self.assertGreaterEqual(len(pins), 20)
        for direct in ("faster-whisper", "av", "ctranslate2", "huggingface-hub", "onnxruntime"):
            self.assertIn(direct, pins)
        self.assertTrue(pins["av"].startswith("18."), "faster-whisper 1.2.1 needs PyAV <19")

    def test_bootstrap_never_auto_upgrades_build_tools_or_uses_sdists(self):
        bootstrap = (ROOT / "scripts/bootstrap.sh").read_text()
        self.assertIn("--only-binary=:all:", bootstrap)
        self.assertIn('pip check', bootstrap)
        self.assertIn('-r "$ROOT/requirements.txt"', bootstrap)
        self.assertNotIn("pip install -U pip wheel", bootstrap)


if __name__ == "__main__":
    unittest.main()
