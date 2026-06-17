import tempfile
import unittest
from pathlib import Path

from self_healing.patching.safety import resolve_safe_path


class SafetyTests(unittest.TestCase):
    def test_allows_configured_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = resolve_safe_path(tmp, "src/app.py", ["src"])
            self.assertEqual(path, Path(tmp).resolve() / "src/app.py")

    def test_rejects_path_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                resolve_safe_path(tmp, "../secret.txt", ["src"])

    def test_rejects_disallowed_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                resolve_safe_path(tmp, "other.py", ["src"])


if __name__ == "__main__":
    unittest.main()
