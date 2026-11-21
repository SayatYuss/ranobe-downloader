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
            self.assertEqual(a.settings["default_format"], "epub")
            self.assertEqual(a.settings["image_mode"], "original")
            self.assertEqual(a.settings["image_quality"], 85)
            self.assertEqual(a.settings["image_max_width"], 1600)
            a.settings["directory"] = dirname
            a.settings["default_format"] = "html"
            a.settings["image_mode"] = "optimized"
            a.settings["image_quality"] = 72
            a.settings["image_max_width"] = 1280
            a.save_settings()
            output = root / "test.epub"
            output.write_bytes(b"example")
            a.add_download(title="Example", path=output, fmt="epub")
            b = Store(root)
            self.assertEqual(b.settings["directory"], dirname)
            self.assertEqual(b.settings["default_format"], "html")
            self.assertEqual(b.settings["image_mode"], "optimized")
            self.assertEqual(b.settings["image_quality"], 72)
            self.assertEqual(b.settings["image_max_width"], 1280)
            self.assertEqual(len(b.history), 1)
            self.assertEqual(b.history[0]["size"], 7)
            self.assertEqual(b.history[0]["format"], "epub")
            self.assertTrue((root / "history.json").is_file())

    def test_invalid_download_preferences_are_normalized(self):
        from interfaces.pyside6.storage import Store
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            (root / "settings.json").write_text(json.dumps({
                "default_format": "pdf",
                "image_mode": "lossless",
                "image_quality": True,
                "image_max_width": 99999,
            }), encoding="utf-8")
            store = Store(root)
            self.assertEqual(store.settings["default_format"], "epub")
            self.assertEqual(store.settings["image_mode"], "original")
            self.assertEqual(store.settings["image_quality"], 85)
            self.assertEqual(store.settings["image_max_width"], 4096)

if __name__ == "__main__":
    unittest.main()
