"""Desktop regressions: cancellation, GUI dispatch and repeat selection."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import importlib.util
import tempfile
import time
import unittest
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import patch

if importlib.util.find_spec("PySide6") is None:
    raise unittest.SkipTest("PySide6 optional dependency is absent")

from PySide6.QtCore import QThread
from PySide6.QtWidgets import QApplication
from interfaces.pyside6.app import Window, perform_download, DownloadCancelled
from interfaces.pyside6.storage import Store
from interfaces.pyside6.theme import apply_theme


class PolishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patches = [patch('interfaces.pyside6.app.Store', lambda: Store(Path(self.temp.name))),
                        patch('interfaces.pyside6.app.KeyringTokenStorage'),
                        patch('interfaces.pyside6.app.configure_logging')]
        self.patches[0].start()
        self.patches[1].start().return_value.load.return_value = None
        self.patches[2].start()
        self.window = Window()

    def tearDown(self):
        self.window.exiting = True
        self.window.tray.hide()
        self.window.close()
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def test_cancel_before_download(self):
        task = SimpleNamespace(cancel=Event())
        task.cancel.set()
        with patch('interfaces.pyside6.app.Downloader') as downloader:
            with self.assertRaises(DownloadCancelled):
                perform_download(task, None, None, 'txt', None, None, None, None, None)
            downloader.assert_not_called()

    def test_repeat_all_resets_previous_range(self):
        self.window.translation_ids = [7]
        self.window.start.addItem('first', 1)
        self.window.end.addItem('last', 2)
        self.window.scope.setCurrentIndex(3)
        self.window.repeat_record = {'format': 'txt'}
        with patch.object(self.window, 'enqueue') as enqueue:
            self.window.apply_repeat_selection()
            self.assertEqual(self.window.scope.currentIndex(), 0)
            enqueue.assert_called_once()

    def test_missing_repeat_chapter_does_not_enqueue(self):
        self.window.translation_ids = [7]
        self.window.repeat_record = {'start_id': 99}
        with patch.object(self.window, 'enqueue') as enqueue, patch('interfaces.pyside6.app.QMessageBox.warning'):
            self.window.apply_repeat_selection()
            enqueue.assert_not_called()

    def test_task_result_delivered_on_gui_thread(self):
        received = []
        self.window.run_task(lambda task: 'ok', on_done=lambda result: received.append((result, QThread.currentThread())))
        deadline = time.monotonic() + 5
        while self.window.threads and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(.005)
        self.assertFalse(self.window.threads)
        self.assertEqual(received, [('ok', self.app.thread())])

    def test_theme_changes_and_restores_system(self):
        for mode in ('dark', 'light', 'system'):
            apply_theme(self.app, mode)
            self.assertEqual(self.app._desktop_theme_mode, mode)


if __name__ == '__main__':
    unittest.main()
