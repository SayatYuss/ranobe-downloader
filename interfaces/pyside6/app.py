"""Native Qt desktop application, separate from the CLI and web interfaces."""
from __future__ import annotations

import importlib.metadata
import logging
import shutil
import sys
from collections import deque
from threading import Event
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit,
    QProgressBar, QPushButton, QSystemTrayIcon, QTabWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget, QMenu, QAbstractItemView,
)

from core.auth.storage import KeyringTokenStorage
from providers.libsocial.client import LibSocialClient
from providers.libsocial.cover import download_cover
from ranobe_downloader import Downloader
from interfaces.pyside6.storage import Store, configure_logging
from interfaces.pyside6.theme import apply_theme

log = logging.getLogger(__name__)
GITHUB = "https://github.com/SayatYuss"


class Task(QObject):
    done = Signal(object)
    progress = Signal(int, int, str)
    failed = Signal(str)

    def __init__(self, operation, *args):
        super().__init__()
        self.operation, self.args = operation, args
        self.cancel = Event()

    def run(self):
        try:
            self.done.emit(self.operation(self, *self.args))
        except Exception as exc:
            log.exception("Desktop task failed")
            self.failed.emit(str(exc))


def lookup(task, reference, token):
    with Downloader(token=token) as downloader:
        book = downloader.get_book(reference)
    cover = None
    try:
        url = getattr(book._plan.title, "cover_url", None)
        if url:
            cover, _ = download_cover(url)
    except Exception:
        log.info("Cover unavailable", exc_info=True)
    return book, cover


def verify_token(task, token):
    with LibSocialClient(token) as client:
        user = client.get_current_user()
    return user["username"]


class DownloadCancelled(Exception):
    def __str__(self):
        return "CANCELLED: download interrupted"


def perform_download(task, book, branch, fmt, start_id, end_id, path, cache, token):
    def check_cancel(*_):
        if task.cancel.is_set():
            raise DownloadCancelled()

    def progress(current, total, chapter):
        check_cancel()
        task.progress.emit(current, total, chapter)

    check_cancel()
    with Downloader(token=token) as downloader:
        return downloader.download(
            book, branch_id=branch, format=fmt, output=path,
            chapter_start_id=start_id, chapter_end_id=end_id,
            cache_dir=cache, resume=True,
            progress=progress, status=check_cancel,
        )


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.store = Store()
        configure_logging(self.store.root)
        self.token_store = KeyringTokenStorage()
        self.book = None
        self.chapters = ()
        self.translation_ids = []
        self.pending = deque()
        self.current = None
        self.current_task = None
        self.active_paths = set()
        self.history_indices = []
        self.repeat_record = None
        self.lookup_pending = False
        self.running = False
        self.threads = []
        self.tasks = []
        self.exiting = False
        self.setWindowTitle("Ranobe Downloader")
        self.resize(870, 600)
        self.setAcceptDrops(True)

        wrapper = QWidget()
        main = QVBoxLayout(wrapper)
        main.setContentsMargins(24, 20, 24, 18)
        main.setSpacing(16)
        header = QHBoxLayout()
        header.addWidget(QLabel("<b>Ranobe Downloader</b>"))
        header.addStretch()
        self.username = QLabel("Не авторизован")
        header.addWidget(self.username)
        main.addLayout(header)
        self.tabs = QTabWidget()
        main.addWidget(self.tabs)
        self.setCentralWidget(wrapper)

        download = QWidget()
        form = QFormLayout(download)
        form.setContentsMargins(12, 18, 12, 12)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        ref_line = QHBoxLayout()
        self.reference = QLineEdit()
        self.reference.setPlaceholderText("Ссылка на RanobeLib")
        ref_line.addWidget(self.reference)
        find = self.find_button = QPushButton("Найти")
        find.clicked.connect(self.find_book)
        ref_line.addWidget(find)
        form.addRow("Ссылка", ref_line)
        self.title_label = QLabel("—")
        self.title_label.setWordWrap(True)
        form.addRow("Название", self.title_label)
        self.cover = QLabel()
        self.cover.setFixedSize(90, 125)
        self.cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        form.addRow("Обложка", self.cover)
        self.translation = QComboBox()
        self.translation.currentIndexChanged.connect(self.translation_changed)
        form.addRow("Перевод", self.translation)
        self.scope = QComboBox()
        self.scope.addItems(["Все главы", "Первые 10", "Последние 10", "Диапазон"])
        self.scope.currentIndexChanged.connect(self.update_scope)
        form.addRow("Главы", self.scope)
        range_row = QHBoxLayout()
        self.start = QComboBox()
        self.end = QComboBox()
        range_row.addWidget(self.start)
        range_row.addWidget(QLabel("—"))
        range_row.addWidget(self.end)
        form.addRow("Диапазон", range_row)
        self.fmt = QComboBox()
        self.fmt.addItems(["epub", "txt", "html"])
        form.addRow("Формат", self.fmt)
        self.add_button = QPushButton("В очередь")
        self.add_button.clicked.connect(self.enqueue)
        form.addRow("", self.add_button)
        self.progress = QProgressBar()
        form.addRow("Прогресс", self.progress)
        self.status = QLabel("Готово")
        form.addRow("", self.status)
        self.tabs.addTab(download, "Скачать")

        queue_page = QWidget()
        queue_layout = QVBoxLayout(queue_page)
        self.queue_table = QTableWidget(0, 3)
        self.queue_table.setHorizontalHeaderLabels(["Книга", "Формат", "Состояние"])
        self.queue_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.queue_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.queue_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.queue_table.horizontalHeader().setStretchLastSection(True)
        queue_layout.addWidget(self.queue_table)
        queue_controls = QHBoxLayout()
        self.cancel_button = QPushButton("Отменить текущую")
        self.cancel_button.clicked.connect(self.cancel_current)
        remove_queue_button = QPushButton("Удалить из очереди")
        remove_queue_button.clicked.connect(self.remove_pending)
        queue_controls.addWidget(self.cancel_button)
        queue_controls.addWidget(remove_queue_button)
        queue_controls.addStretch()
        queue_layout.addLayout(queue_controls)
        self.tabs.addTab(queue_page, "Очередь")

        history_page = QWidget()
        history_layout = QVBoxLayout(history_page)
        self.history_filter = QLineEdit()
        self.history_filter.setPlaceholderText("Поиск по истории")
        self.history_filter.textChanged.connect(self.reload_history)
        history_layout.addWidget(self.history_filter)
        self.history = QTableWidget(0, 4)
        self.history.setHorizontalHeaderLabels(["Название", "Формат", "Дата", "Размер"])
        self.history.horizontalHeader().setStretchLastSection(True)
        self.history.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.history.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.history.cellDoubleClicked.connect(self.open_history)
        history_layout.addWidget(self.history)
        open_btn = QPushButton("Открыть файл")
        open_btn.clicked.connect(self.open_selected_history)
        controls = QHBoxLayout()
        controls.addWidget(open_btn)
        folder_btn = QPushButton("Открыть папку")
        folder_btn.clicked.connect(self.open_history_folder)
        controls.addWidget(folder_btn)
        delete_btn = QPushButton("Удалить запись")
        delete_btn.clicked.connect(self.delete_history_record)
        controls.addWidget(delete_btn)
        repeat_btn = QPushButton("Повторить")
        repeat_btn.clicked.connect(self.redownload_history)
        controls.addWidget(repeat_btn)
        controls.addStretch()
        history_layout.addLayout(controls)
        self.tabs.addTab(history_page, "История")

        settings_page = QWidget()
        settings_form = QFormLayout(settings_page)
        self.directory = QLineEdit(self.store.settings.get("directory", ""))
        browse = QPushButton("Обзор…")
        browse.clicked.connect(self.choose_dir)
        directory_row = QHBoxLayout()
        directory_row.addWidget(self.directory)
        directory_row.addWidget(browse)
        settings_form.addRow("Папка загрузок", directory_row)
        self.directory.editingFinished.connect(self.save_dir)
        self.theme_box = QComboBox()
        self.theme_box.addItems(["Системная", "Светлая", "Тёмная"])
        self.theme_box.setCurrentIndex({"system": 0, "light": 1, "dark": 2}.get(self.store.settings.get("theme", "system"), 0))
        self.theme_box.currentIndexChanged.connect(self.change_theme)
        settings_form.addRow("Тема", self.theme_box)
        settings_form.addRow("Кеш", QLabel(str(self.store.cache)))
        clear = QPushButton("Очистить кеш")
        clear.clicked.connect(self.clear_cache)
        settings_form.addRow("", clear)
        self.token_input = QLineEdit()
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_input.setPlaceholderText("Bearer token")
        settings_form.addRow("Токен", self.token_input)
        auth_row = QHBoxLayout()
        connect = QPushButton("Войти")
        connect.clicked.connect(self.login)
        logout = QPushButton("Выйти")
        logout.clicked.connect(self.logout)
        auth_row.addWidget(connect)
        auth_row.addWidget(logout)
        settings_form.addRow("", auth_row)
        version = importlib.metadata.version("ranobe-downloader")
        link = QLabel(f'Версия {version} · <a href="{GITHUB}">GitHub SayatYuss</a>')
        link.setOpenExternalLinks(True)
        settings_form.addRow("О программе", link)
        log_button = QPushButton("Открыть журнал")
        log_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.store.root / "desktop.log"))))
        settings_form.addRow("Диагностика", log_button)
        self.tabs.addTab(settings_page, "Настройки")

        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon))
        menu = QMenu()
        show = QAction("Открыть", self)
        show.triggered.connect(self.restore_from_tray)
        menu.addAction(show)
        quit_action = QAction("Выход", self)
        quit_action.triggered.connect(self.quit_app)
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.tray_activated)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()
        self.reload_history()
        self.update_scope()
        if self.token_store.load():
            self.run_task(verify_token, self.token_store.load(), on_done=self.set_user, busy=False)

    def run_task(self, operation, *args, on_done, busy=True, on_failure=None):
        thread = QThread(self)
        task = Task(operation, *args)
        task.moveToThread(thread)
        thread.started.connect(task.run)
        task.on_done = on_done
        task.on_failure = on_failure or self.report_error
        task.done.connect(self.task_done)
        task.failed.connect(self.task_failed)
        task.done.connect(thread.quit)
        task.failed.connect(thread.quit)
        thread.finished.connect(task.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: self.tasks.remove(task) if task in self.tasks else None)
        self.threads.append(thread)
        if operation == perform_download:
            self.current_task = task
        self.tasks.append(task)
        thread.finished.connect(lambda: self.threads.remove(thread) if thread in self.threads else None)
        if operation == perform_download:
            task.progress.connect(self.on_progress)
        thread.start()
        self.update_queue()

    @Slot(object)
    def task_done(self, result):
        self.sender().on_done(result)

    @Slot(str)
    def task_failed(self, message):
        self.sender().on_failure(message)

    def report_error(self, message):
        self.status.setText("Ошибка: " + message)
        QMessageBox.warning(self, "Ошибка", message)

    def find_book(self):
        reference = self.reference.text().strip()
        if not reference or self.lookup_pending:
            return
        self.lookup_pending = True
        self.find_button.setEnabled(False)
        self.add_button.setEnabled(False)
        self.status.setText("Загрузка данных…")
        self.run_task(lookup, reference, self.token_store.load(), on_done=self.book_loaded, on_failure=self.lookup_failed)

    def lookup_failed(self, message):
        self.lookup_pending = False
        self.find_button.setEnabled(True)
        self.add_button.setEnabled(True)
        self.repeat_record = None
        self.report_error(message)

    def book_loaded(self, result):
        self.lookup_pending = False
        self.find_button.setEnabled(True)
        self.add_button.setEnabled(True)
        self.scope.setCurrentIndex(0)
        self.book, cover = result
        self.title_label.setText(self.book.title)
        self.cover.clear()
        if cover:
            pixmap = QPixmap()
            if pixmap.loadFromData(cover):
                self.cover.setPixmap(pixmap.scaled(self.cover.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.translation.blockSignals(True)
        self.translation.clear()
        self.translation_ids = [t.branch_id for t in self.book.translations]
        for t in self.book.translations:
            self.translation.addItem(f"{t.name or 'Перевод'} ({t.chapter_count})")
        if not self.translation_ids:
            self.translation_ids = [None]
            self.translation.addItem("Без выбора перевода")
        self.translation.blockSignals(False)
        self.translation_changed()
        self.status.setText("Готово")
        if self.repeat_record is not None:
            self.apply_repeat_selection()

    def apply_repeat_selection(self):
        record = self.repeat_record
        self.repeat_record = None
        branch = record.get("branch_id")
        if branch is not None and branch not in self.translation_ids:
            QMessageBox.warning(self, "Повторить", "Сохранённый перевод больше недоступен")
            return
        if branch in self.translation_ids:
            self.translation.setCurrentIndex(self.translation_ids.index(branch))
        start, end = record.get("start_id"), record.get("end_id")
        if any(value is not None and self.start.findData(value) < 0 for value in (start, end)):
            QMessageBox.warning(self, "Повторить", "Сохранённый диапазон больше недоступен")
            return
        self.scope.setCurrentIndex(0)
        if start is not None or end is not None:
            self.scope.setCurrentIndex(3)
            if start is not None:
                index = self.start.findData(start)
                if index >= 0:
                    self.start.setCurrentIndex(index)
            if end is not None:
                index = self.end.findData(end)
                if index >= 0:
                    self.end.setCurrentIndex(index)
        fmt = record.get("format", "epub")
        pos = self.fmt.findText(fmt)
        if pos >= 0:
            self.fmt.setCurrentIndex(pos)
        self.enqueue()

    def translation_changed(self):
        if not self.book:
            return
        i = self.translation.currentIndex()
        if i < 0:
            return
        self.chapters = self.book.list_chapters(self.translation_ids[i])
        for widget in (self.start, self.end):
            widget.clear()
            for ch in self.chapters:
                widget.addItem(f"Том {ch['volume']}, глава {ch['number']}: {ch['name'] or ''}", ch["id"])
        if self.chapters:
            self.end.setCurrentIndex(len(self.chapters) - 1)
        self.update_scope()

    def update_scope(self):
        enabled = self.scope.currentIndex() == 3
        self.start.setEnabled(enabled)
        self.end.setEnabled(enabled)

    def enqueue(self):
        if self.lookup_pending or not self.book or not self.chapters:
            QMessageBox.warning(self, "Главы", "Не выбраны главы")
            return
        branch = self.translation_ids[self.translation.currentIndex()]
        mode = self.scope.currentIndex()
        start = end = None
        if mode == 1:
            end = self.chapters[min(9, len(self.chapters) - 1)]["id"]
        elif mode == 2:
            start = self.chapters[max(0, len(self.chapters) - 10)]["id"]
        elif mode == 3:
            if self.start.currentIndex() > self.end.currentIndex():
                QMessageBox.warning(self, "Диапазон", "Начало позже конца")
                return
            start, end = self.start.currentData(), self.end.currentData()
        directory = Path(self.directory.text()).expanduser()
        directory.mkdir(parents=True, exist_ok=True)
        fmt = self.fmt.currentText()
        base = directory / f"{self.book.slug_url}_{branch if branch is not None else 'default'}.{fmt}"
        path = base
        number = 1
        while path.exists() or path in self.active_paths or any(item[5] == path for item in self.pending):
            path = base.with_name(f"{base.stem}_{number}{base.suffix}")
            number += 1
        self.pending.append((self.book, branch, fmt, start, end, path))
        self.update_queue()
        self.run_next()

    def update_queue(self):
        rows = ([self.current] if self.current else []) + list(self.pending)
        self.queue_table.setRowCount(len(rows))
        for row, entry in enumerate(rows):
            book, branch, fmt, start, end, path = entry
            for col, value in enumerate((book.title, fmt.upper(), "Скачивается" if row == 0 and self.current else "Ожидает")):
                self.queue_table.setItem(row, col, QTableWidgetItem(value))
        self.cancel_button.setEnabled(self.current_task is not None)

    def remove_pending(self):
        selected = self.queue_table.currentRow()
        index = selected - (1 if self.current else 0)
        if index < 0 or index >= len(self.pending):
            return
        del self.pending[index]
        self.update_queue()

    def cancel_current(self):
        if self.current_task:
            self.current_task.cancel.set()
            self.status.setText("Отмена после текущей операции…")
            self.queue_table.setItem(0, 2, QTableWidgetItem("Отменяется"))
            self.cancel_button.setEnabled(False)

    def run_next(self):
        if self.running or not self.pending:
            self.update_queue()
            return
        book, branch, fmt, start, end, path = self.pending.popleft()
        self.current = (book, branch, fmt, start, end, path)
        self.active_paths.add(path)
        self.running = True
        self.progress.setValue(0)
        self.status.setText(f"Скачивание: {book.title}")
        self.update_queue()
        def completed(saved):
            self.running = False
            self.current_task = None
            self.current = None
            self.active_paths.discard(path)
            self.store.add_download(title=book.title, path=Path(saved), fmt=fmt, reference=book.slug_url, branch_id=branch, start_id=start, end_id=end)
            self.reload_history()
            self.status.setText(f"Сохранено: {saved}")
            if self.tray.isVisible():
                self.tray.showMessage("Ranobe Downloader", f"Загрузка завершена: {book.title}")
            self.run_next()
        def failed(message):
            self.running = False
            self.current_task = None
            self.current = None
            self.active_paths.discard(path)
            if message.startswith("CANCELLED:"):
                self.status.setText("Отменено")
            else:
                self.status.setText("Ошибка загрузки")
                QMessageBox.warning(self, "Ошибка", message)
            self.run_next()
        self.run_task(perform_download, book, branch, fmt, start, end, path, self.store.cache,
                      self.token_store.load(), on_done=completed, on_failure=failed)

    def on_progress(self, current, total, chapter):
        self.progress.setValue(round(current * 100 / total) if total else 0)
        self.status.setText(f"{current}/{total} — {chapter}")

    def reload_history(self):
        query = self.history_filter.text().strip().casefold()
        self.history_indices = [i for i, item in enumerate(self.store.history) if query in item.get("title", "").casefold() or query in item.get("format", "").casefold()]
        self.history.setRowCount(len(self.history_indices))
        for row, index in enumerate(self.history_indices):
            record = self.store.history[index]
            for col, key in enumerate(("title", "format", "date", "size")):
                value = record.get(key, "")
                if key == "size":
                    value = f"{value / 1048576:.1f} MiB"
                item = QTableWidgetItem(str(value))
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, record.get("path"))
                self.history.setItem(row, col, item)

    def open_history(self, row, _column):
        item = self.history.item(row, 0)
        if item:
            path = Path(item.data(Qt.ItemDataRole.UserRole))
            if path.exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
            else:
                QMessageBox.information(self, "Файл", "Файл был перемещён или удалён")

    def open_selected_history(self):
        row = self.history.currentRow()
        if row >= 0:
            self.open_history(row, 0)

    def selected_history_index(self):
        row = self.history.currentRow()
        return self.history_indices[row] if 0 <= row < len(self.history_indices) else None

    def open_history_folder(self):
        index = self.selected_history_index()
        if index is not None:
            path = Path(self.store.history[index]["path"]).parent
            if path.exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def delete_history_record(self):
        index = self.selected_history_index()
        if index is not None:
            del self.store.history[index]
            self.store.save_history()
            self.reload_history()

    def redownload_history(self):
        index = self.selected_history_index()
        if index is not None:
            record = self.store.history[index]
            reference = record.get("reference")
            if not reference:
                QMessageBox.information(self, "Повторить", "Для старой записи не сохранена ссылка на произведение.")
                return
            self.repeat_record = dict(record)
            self.reference.setText(reference)
            self.tabs.setCurrentIndex(0)
            self.find_book()

    def change_theme(self):
        mode = ("system", "light", "dark")[self.theme_box.currentIndex()]
        self.store.settings["theme"] = mode
        self.store.save_settings()
        apply_theme(QApplication.instance(), mode)

    def choose_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Папка загрузок", self.directory.text())
        if path:
            self.directory.setText(path)
            self.save_dir()

    def save_dir(self):
        self.store.settings["directory"] = self.directory.text()
        self.store.save_settings()

    def clear_cache(self):
        if self.running or self.pending:
            QMessageBox.information(self, "Кеш", "Дождитесь завершения загрузок")
            return
        shutil.rmtree(self.store.cache, ignore_errors=True)
        self.store.cache.mkdir(exist_ok=True)

    def set_user(self, username):
        self.username.setText(username)
        self.token_input.clear()

    def login(self):
        token = self.token_input.text().strip()
        if token.lower().startswith("bearer "):
            token = token[7:].strip()
        if not token:
            return
        def success(username):
            self.token_store.save(token)
            self.set_user(username)
        self.run_task(verify_token, token, on_done=success)

    def logout(self):
        self.token_store.delete()
        self.username.setText("Не авторизован")
        self.token_input.clear()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        value = urls[0].toString() if urls else event.mimeData().text().strip()
        if value.startswith("https://"):
            self.reference.setText(value)
            self.tabs.setCurrentIndex(0)
            self.find_book()
            event.acceptProposedAction()

    def tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.restore_from_tray()

    def restore_from_tray(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        if not self.exiting and self.tray.isVisible():
            self.hide()
            event.ignore()
        elif self.running or self.pending or self.threads:
            QMessageBox.information(self, "Загрузка", "Дождитесь завершения фоновых операций")
            event.ignore()
        else:
            event.accept()

    def quit_app(self):
        if self.running or self.pending or self.threads:
            QMessageBox.information(self, "Загрузка", "Дождитесь завершения фоновых операций")
            return
        self.exiting = True
        self.tray.hide()
        QApplication.quit()


def main():
    if "--check" in sys.argv:
        import PySide6
        from ranobe_downloader import Downloader
        return 0
    app = QApplication(sys.argv)
    app.setApplicationName("RanobeDownloader")
    app.setQuitOnLastWindowClosed(not QSystemTrayIcon.isSystemTrayAvailable())
    window = Window()
    apply_theme(app, window.store.settings.get("theme", "system"))
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

