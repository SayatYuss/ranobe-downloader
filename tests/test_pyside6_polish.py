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

from PySide6.QtCore import QCoreApplication, QEvent, QThread
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QDialog
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
        self.window = Window(False)

    def tearDown(self):
        self.window.exiting = True
        self.window.tray.hide()
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()
        self.window = None
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def test_cancel_before_download(self):
        task = SimpleNamespace(cancel=Event())
        task.cancel.set()
        with patch('interfaces.pyside6.tasks.Downloader') as downloader:
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
        with patch.object(self.window, 'enqueue') as enqueue, patch('interfaces.pyside6.pages.download.QMessageBox.warning'):
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

    def test_compact_queue_status_and_clear(self):
        self.assertTrue(self.window.cancel_button.isHidden())
        self.assertTrue(self.window.clear_queue_button.isHidden())
        entry = (SimpleNamespace(title='Book'), None, 'epub', None, None, Path('book.epub'))
        self.window.pending.append(entry)
        self.window.update_queue()
        self.assertEqual(self.window.queue_status.text(), 'Ожидают загрузки: 1')
        self.assertTrue(self.window.clear_queue_button.isEnabled())
        self.assertFalse(self.window.clear_queue_button.isHidden())

        self.window.clear_pending()
        self.assertEqual(self.window.queue_status.text(), 'Очередь пуста')
        self.assertFalse(self.window.pending)
        self.assertTrue(self.window.clear_queue_button.isHidden())

    def test_lookup_state_disables_book_controls_and_shows_progress(self):
        self.assertFalse(self.window.translation.isEnabled())
        self.assertFalse(self.window.scope.isEnabled())
        self.assertFalse(self.window.fmt.isEnabled())
        self.assertFalse(self.window.add_button.isEnabled())
        self.assertTrue(self.window.lookup_progress.isHidden())

        self.window.set_lookup_busy(True)
        self.assertEqual(self.window.find_button.text(), 'Поиск…')
        self.assertFalse(self.window.lookup_progress.isHidden())

        self.window.book = SimpleNamespace()
        self.window.set_lookup_busy(False)
        self.assertEqual(self.window.find_button.text(), 'Найти')
        self.assertTrue(self.window.lookup_progress.isHidden())
        self.assertTrue(self.window.translation.isEnabled())
        self.assertTrue(self.window.scope.isEnabled())
        self.assertTrue(self.window.fmt.isEnabled())
        self.assertTrue(self.window.add_button.isEnabled())

    def test_cover_preview_requires_loaded_pixmap(self):
        with patch.object(QDialog, 'exec') as execute:
            self.window.show_cover_preview()
            execute.assert_not_called()

            self.window.cover_pixmap = QPixmap(40, 60)
            self.window.cover_pixmap.fill()
            self.window.show_cover_preview()
            execute.assert_called_once()

    def test_format_buttons_and_book_metadata(self):
        translation = SimpleNamespace(branch_id=7, name='Team', chapter_count=12)
        book = SimpleNamespace(
            title='Example Book', authors=('Author One', 'Author Two'),
            chapter_count=12, translations=(translation,),
            list_chapters=lambda branch_id: ({
                'id': 1, 'volume': '1', 'number': '1', 'name': 'Start',
            },),
        )
        self.window.book_loaded((book, None))

        self.assertFalse(self.window.book_details.isHidden())
        self.assertIn('Автор: Author One, Author Two', self.window.book_details.text())
        self.assertIn('Глав: 12', self.window.book_details.text())
        self.assertIn('Перевод: Team', self.window.book_details.text())
        self.assertIn('Обложка: недоступна', self.window.book_details.text())
        self.assertEqual(self.window.fmt.currentText(), 'epub')

        self.window.fmt.buttons[2].click()
        self.assertEqual(self.window.fmt.currentText(), 'html')
        self.assertTrue(self.window.fmt.buttons[2].isChecked())

    def test_history_empty_search_and_contextual_actions(self):
        self.assertFalse(self.window.history_empty.isHidden())
        self.assertTrue(self.window.history.isHidden())
        self.assertTrue(self.window.history_actions.isHidden())

        self.window.store.history = [{
            'title': 'Example Book', 'format': 'epub',
            'date': '2026-11-21T12:30:00+06:00', 'size': 2 * 1048576,
            'path': str(Path(self.temp.name) / 'example.epub'),
        }]
        self.window.reload_history()
        self.assertEqual(self.window.history_count.text(), '1 файл')
        self.assertFalse(self.window.history.isHidden())
        self.assertTrue(self.window.history_empty.isHidden())
        self.assertEqual(self.window.history.item(0, 1).text(), 'EPUB')
        self.assertEqual(self.window.history.item(0, 2).text(), '21.11.2026 · 12:30')

        self.window.history.selectRow(0)
        self.assertFalse(self.window.history_actions.isHidden())

        self.window.history_filter.setText('missing')
        self.assertEqual(self.window.history_empty_title.text(), 'Ничего не найдено')
        self.assertTrue(self.window.history_actions.isHidden())

    def test_non_modal_toast(self):
        self.assertTrue(self.window.toast.isHidden())
        self.window.show_toast('Готово', timeout=10000)
        self.assertFalse(self.window.toast.isHidden())
        self.assertEqual(self.window.toast.label.text(), 'Готово')

    def test_cache_size_is_displayed_and_refreshed(self):
        cached = self.window.store.cache / 'chapter.bin'
        cached.write_bytes(b'x' * 1048576)
        self.window.refresh_cache_size()
        self.assertEqual(self.window.cache_size_label.text(), 'Использовано: 1.0 MiB')

        self.window.clear_cache()
        self.assertEqual(self.window.cache_size_label.text(), 'Использовано: 0 B')
        self.assertEqual(self.window.toast.label.text(), 'Кеш очищен')

    def test_authorized_state_hides_token_entry(self):
        self.assertEqual(self.window.auth_status.text(), 'Не авторизован')
        self.assertFalse(self.window.token_entry.isHidden())
        self.assertTrue(self.window.logout_button.isHidden())

        self.window.set_user('reader')
        self.assertEqual(self.window.auth_status.text(), 'Авторизован: reader')
        self.assertTrue(self.window.token_entry.isHidden())
        self.assertTrue(self.window.login_button.isHidden())
        self.assertFalse(self.window.logout_button.isHidden())

    def test_download_preferences_update_ui_and_store(self):
        self.window.default_format_box.setCurrentIndex(
            self.window.default_format_box.findData('html')
        )
        self.assertEqual(self.window.store.settings['default_format'], 'html')
        self.assertEqual(self.window.fmt.currentText(), 'html')

        self.assertFalse(self.window.image_quality.isEnabled())
        self.assertFalse(self.window.image_max_width.isEnabled())
        self.window.image_mode_box.setCurrentIndex(
            self.window.image_mode_box.findData('optimized')
        )
        self.window.image_quality.setValue(72)
        self.window.image_max_width.setValue(1280)
        self.window.save_image_settings()

        self.assertTrue(self.window.image_quality.isEnabled())
        self.assertTrue(self.window.image_max_width.isEnabled())
        self.assertEqual(self.window.store.settings['image_mode'], 'optimized')
        self.assertEqual(self.window.store.settings['image_quality'], 72)
        self.assertEqual(self.window.store.settings['image_max_width'], 1280)

        restored = Store(Path(self.temp.name))
        self.assertEqual(restored.settings['default_format'], 'html')
        self.assertEqual(restored.settings['image_mode'], 'optimized')
        self.assertEqual(restored.settings['image_quality'], 72)
        self.assertEqual(restored.settings['image_max_width'], 1280)

    def test_image_preferences_are_forwarded_to_downloader(self):
        task = SimpleNamespace(cancel=Event(), progress=SimpleNamespace(emit=lambda *_: None))
        with patch('interfaces.pyside6.tasks.Downloader') as downloader:
            downloader.return_value.__enter__.return_value.download.return_value = Path('book.epub')
            result = perform_download(
                task, 'book', 7, 'epub', 1, 10, Path('book.epub'),
                Path('cache'), None, 'optimized', 72, 1280,
            )

        self.assertEqual(result, Path('book.epub'))
        kwargs = downloader.return_value.__enter__.return_value.download.call_args.kwargs
        self.assertEqual(kwargs['image_mode'], 'optimized')
        self.assertEqual(kwargs['image_quality'], 72)
        self.assertEqual(kwargs['image_max_width'], 1280)


if __name__ == '__main__':
    unittest.main()
