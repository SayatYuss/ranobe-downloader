"""Offscreen UI smoke test for the PySide6 desktop."""
import importlib.util
import os
import tempfile
import unittest
from unittest.mock import patch

@unittest.skipUnless(importlib.util.find_spec("PySide6"), "PySide6 optional dependency is absent")
class WindowSmokeTest(unittest.TestCase):
    def test_window_tabs_theme_queue_and_history(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtCore import QCoreApplication, QEvent
        from PySide6.QtWidgets import QApplication
        from interfaces.pyside6.app import Window
        owns_app = QApplication.instance() is None
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as directory:
            with patch("interfaces.pyside6.app.Store") as factory, \
                 patch("interfaces.pyside6.app.KeyringTokenStorage") as keyring:
                from interfaces.pyside6.storage import Store
                factory.side_effect = lambda: Store(__import__("pathlib").Path(directory))
                keyring.return_value.load.return_value = None
                window = Window(False)
                self.assertEqual(window.tabs.count(), 3)
                self.assertEqual(window.history.rowCount(), 0)
                self.assertEqual(window.queue_status.text(), "Очередь пуста")
                self.assertEqual(len(window.settings_cards), 4)
                self.assertTrue(window.settings_scroll.widgetResizable())
                window.theme_box.setCurrentIndex(2)
                self.assertEqual(window.store.settings["theme"], "dark")
                window.theme_box.setCurrentIndex(0)
                window.exiting = True
                window.close()
                window.deleteLater()
                QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                app.processEvents()
        if owns_app:
            app.quit()

if __name__ == "__main__":
    unittest.main()
