"""Persistence checks for optional PySide6 desktop."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

@unittest.skipUnless(importlib.util.find_spec("PySide6"), "PySide6 not installed")
class DesktopStorageTests(unittest.TestCase):
    def test_settings_history_and_cache_survive_restart(self):
        from interfaces.pyside6.storage import Store
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            a = Store(root)
            self.assertTrue(a.cache.is_dir())
            a.settings["directory"] = dirname
            a.save_settings()
            output = root / "test.epub"
            output.write_bytes(b"example")
            a.add_download(title="Example", path=output, fmt="epub")
            b = Store(root)
            self.assertEqual(b.settings["directory"], dirname)
            self.assertEqual(len(b.history), 1)
            self.assertEqual(b.history[0]["size"], 7)
            self.assertEqual(b.history[0]["format"], "epub")
            self.assertTrue((root / "history.json").is_file())

if __name__ == "__main__":
    unittest.main()
