"""Native Qt desktop application, separate from the CLI and web interfaces."""
from __future__ import annotations

import importlib.metadata
import logging
import shutil
import sys
from collections import deque
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit,
    QProgressBar, QPushButton, QSystemTrayIcon, QTabWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget, QMenu,
)

from core.auth.storage import KeyringTokenStorage
from providers.libsocial.client import LibSocialClient
from providers.libsocial.cover import download_cover
from ranobe_downloader import Downloader
from .storage import Store, configure_logging

log = logging.getLogger(__name__)
GITHUB = "https://github.com/SayatYuss"


class Task(QObject):
    done = Signal(object)
    progress = Signal(int, int, str)
    failed = Signal(str)

    def __init__(self, operation, *args):
        super().__init__()
        self.operation, self.args = operation, args

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


def perform_download(task, book, branch, fmt, start_id, end_id, path, cache, token):
    with Downloader(token=token) as downloader:
        return downloader.download(
            book, branch_id=branch, format=fmt, output=path,
            chapter_start_id=start_id, chapter_end_id=end_id,
            cache_dir=cache, resume=True,
            progress=lambda a, b, name: task.progress.emit(a, b, name),
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
        self.running = False
        self.threads = []
        self.exiting = False
        self.setWindowTitle("Ranobe Downloader")
        self.resize(790, 560)
        self.setAcceptDrops(True)

        wrapper = QWidget()
        main = QVBoxLayout(wrapper)
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
        ref_line = QHBoxLayout()
        self.reference = QLineEdit()
        self.reference.setPlaceholderText("Ссылка на RanobeLib")
        ref_line.addWidget(self.reference)
        find = QPushButton("Найти")
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
        self.queue_list = QPlainTextEdit()
        self.queue_list.setReadOnly(True)
        queue_layout.addWidget(self.queue_list)
        self.tabs.addTab(queue_page, "Очередь")

        history_page = QWidget()
        history_layout = QVBoxLayout(history_page)
        self.history = QTableWidget(0, 4)
        self.history.setHorizontalHeaderLabels(["Название", "Формат", "Дата", "Размер"])
        self.history.horizontalHeader().setStretchLastSection(True)
        self.history.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.history.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.history.cellDoubleClicked.connect(self.open_history)
        history_layout.addWidget(self.history)
        open_btn = QPushButton("Открыть файл")
        open_btn.clicked.connect(self.open_selected_history)
        history_layout.addWidget(open_btn)
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
        show.triggered.connect(self.showNormal)
        menu.addAction(show)
        quit_action = QAction("Выход", self)
        quit_action.triggered.connect(self.quit_app)
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda *_: self.showNormal())
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
        task.done.connect(on_done)
        task.failed.connect(on_failure or self.report_error)
        task.done.connect(thread.quit)
        task.failed.connect(thread.quit)
        thread.finished.connect(task.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self.threads.append(thread)
        thread.finished.connect(lambda: self.threads.remove(thread) if thread in self.threads else None)
        if operation == perform_download:
            task.progress.connect(self.on_progress)
        thread.start()

    def report_error(self, message):
        self.running = False
        self.status.setText("Ошибка: " + message)
        QMessageBox.warning(self, "Ошибка", message)
        self.run_next()

    def find_book(self):
        reference = self.reference.text().strip()
        if not reference:
            return
        self.status.setText("Загрузка данных…")
        self.run_task(lookup, reference, self.token_store.load(), on_done=self.book_loaded)

    def book_loaded(self, result):
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
        if not self.book or not self.chapters:
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
        while path.exists() or any(item[5] == path for item in self.pending):
            path = base.with_name(f"{base.stem}_{number}{base.suffix}")
            number += 1
        self.pending.append((self.book, branch, fmt, start, end, path))
        self.update_queue()
        self.run_next()

    def update_queue(self):
        self.queue_list.setPlainText("\n".join(f"{book.title} · {fmt} → {path.name}" for book, _, fmt, _, _, path in self.pending) or "Очередь пуста")

    def run_next(self):
        if self.running or not self.pending:
            return
        book, branch, fmt, start, end, path = self.pending.popleft()
        self.update_queue()
        self.running = True
        self.progress.setValue(0)
        self.status.setText(f"Скачивание: {book.title}")
        def completed(saved):
            self.running = False
            self.store.add_download(title=book.title, path=Path(saved), fmt=fmt)
            self.reload_history()
            self.status.setText(f"Сохранено: {saved}")
            if self.tray.isVisible():
                self.tray.showMessage("Ranobe Downloader", f"Загрузка завершена: {book.title}")
            self.run_next()
        self.run_task(perform_download, book, branch, fmt, start, end, path, self.store.cache,
                      self.token_store.load(), on_done=completed)

    def on_progress(self, current, total, chapter):
        self.progress.setValue(round(current * 100 / total) if total else 0)
        self.status.setText(f"{current}/{total} — {chapter}")

    def reload_history(self):
        self.history.setRowCount(len(self.store.history))
        for row, record in enumerate(self.store.history):
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

    def choose_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Папка загрузок", self.directory.text())
        if path:
            self.directory.setText(path)
            self.save_dir()

    def save_dir(self):
        self.store.settings["directory"] = self.directory.text()
        self.store.save_settings()

    def clear_cache(self):
        if self.running:
            QMessageBox.information(self, "Кеш", "Дождитесь завершения загрузки")
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

    def closeEvent(self, event):
        if not self.exiting and self.tray.isVisible():
            self.hide()
            event.ignore()
        elif self.running:
            QMessageBox.information(self, "Загрузка", "Дождитесь завершения загрузки")
            event.ignore()
        else:
            event.accept()

    def quit_app(self):
        if self.running:
            QMessageBox.information(self, "Загрузка", "Дождитесь завершения загрузки")
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
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")
    window = Window()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
