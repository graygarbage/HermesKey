"""Only tracked, reviewed files belong in a reproducible release archive."""
import hashlib
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path

BUILDER = Path(__file__).resolve().parents[1] / "scripts/build-release.sh"


class ReleaseArchiveTests(unittest.TestCase):
    def test_clean_checkout_is_reproducible_and_excludes_generated_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            scripts = root / "scripts"
            scripts.mkdir(parents=True)
            shutil.copy2(BUILDER, scripts / BUILDER.name)
            (root / "VERSION").write_text("1.2.3\n")
            (root / "tracked.txt").write_text("reviewed fixture\n")
            (root / ".gitignore").write_text("dist/\n__pycache__/\n")
            subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            subprocess.run(["git", "-C", str(root), "-c", "user.name=Fixture",
                            "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture"], check=True)

            cache = root / "tests/__pycache__"
            cache.mkdir(parents=True)
            (cache / "private.cpython-312.pyc").write_bytes(b"PRIVATE_SYNTHETIC_PATH")
            archive = root / "dist/hermeskey-1.2.3.tar.gz"
            for index in range(2):
                subprocess.run([str(scripts / BUILDER.name)], cwd=root,
                               check=True, capture_output=True)
                with tarfile.open(archive) as bundle:
                    self.assertEqual(set(bundle.getnames()),
                                     {".gitignore", "VERSION", "scripts", "scripts/build-release.sh", "tracked.txt"})
                digest = hashlib.sha256(archive.read_bytes()).hexdigest()
                if index == 0:
                    first_digest = digest
                else:
                    self.assertEqual(digest, first_digest)

            untracked = root / "private-untracked.env"
            untracked.write_text("PRIVATE_SYNTHETIC_PATH")
            result = subprocess.run([str(scripts / BUILDER.name)], cwd=root,
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("clean Git checkout", result.stderr)
            self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), first_digest)
            self.assertTrue(untracked.is_file())


if __name__ == "__main__":
    unittest.main()
