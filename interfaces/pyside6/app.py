"""Native Qt desktop application, separate from the CLI and web interfaces."""
from __future__ import annotations

import importlib.metadata
import logging
import shutil
import sys
import httpx
import html
from packaging.version import Version
from collections import deque
from threading import Event
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout,
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit,
    QProgressBar, QPushButton, QSystemTrayIcon, QTabWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget, QMenu, QAbstractItemView, QSizePolicy,
)

from core.auth.storage import KeyringTokenStorage
from providers.libsocial.client import LibSocialClient
from providers.libsocial.cover import download_cover
from ranobe_downloader import Downloader
from interfaces.pyside6.storage import Store, configure_logging
from interfaces.pyside6.theme import apply_theme

log = logging.getLogger(__name__)
GITHUB = "https://github.com/SayatYuss"
RELEASES_API = (
    "https://api.github.com/repos/"
    "SayatYuss/ranobe-downloader/releases/latest"
)


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

def check_latest_release(task, current_version):
    response = httpx.get(
        RELEASES_API,
        headers={"Accept": "application/vnd.github+json"},
        timeout=5,
    )
    response.raise_for_status()

    release = response.json()
    latest = Version(release["tag_name"].removeprefix("v"))
    current = Version(current_version)

    if latest <= current:
        return None

    return {
        "version": str(latest),
        "url": release["html_url"],
        "notes": release.get("body", ""),
    }


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
    def __init__(self, check_update_on_startup: bool = True):
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
        self.resize(980, 700)
        self.setMinimumSize(840, 700)
        self.setAcceptDrops(True)

        wrapper = QWidget()
        wrapper.setObjectName("appShell")
        main = QVBoxLayout(wrapper)
        main.setContentsMargins(28, 22, 28, 22)
        main.setSpacing(18)
        header = QHBoxLayout()
        header.setSpacing(12)
        brand = QVBoxLayout()
        brand.setSpacing(1)
        brand_title = QLabel("Ranobe Downloader")
        brand_title.setObjectName("brandTitle")
        brand_subtitle = QLabel("Личная библиотека — в удобном формате")
        brand_subtitle.setObjectName("mutedText")
        brand.addWidget(brand_title)
        brand.addWidget(brand_subtitle)
        header.addLayout(brand)
        header.addStretch()
        self.username = QLabel("Не авторизован")
        self.username.setObjectName("accountBadge")
        header.addWidget(self.username)
        main.addLayout(header)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        main.addWidget(self.tabs)
        self.setCentralWidget(wrapper)

        download = QWidget()
        download.setObjectName("downloadPage")
        download_layout = QVBoxLayout(download)
        download_layout.setContentsMargins(8, 18, 8, 8)
        download_layout.setSpacing(14)

        page_title = QLabel("Скачать произведение")
        page_title.setObjectName("pageTitle")
        page_hint = QLabel("Вставьте ссылку с RanobeLib — перевод, главы и обложка загрузятся автоматически.")
        page_hint.setObjectName("mutedText")
        page_hint.setWordWrap(True)
        download_layout.addWidget(page_title)
        download_layout.addWidget(page_hint)

        search_card = QFrame()
        search_card.setObjectName("card")
        search_layout = QHBoxLayout(search_card)
        search_layout.setContentsMargins(16, 14, 16, 14)
        search_layout.setSpacing(10)
        self.reference = QLineEdit()
        self.reference.setPlaceholderText("https://ranobelib.me/ru/book/…")
        self.reference.setClearButtonEnabled(True)
        self.reference.returnPressed.connect(self.find_book)
        search_layout.addWidget(self.reference, 1)
        find = self.find_button = QPushButton("Найти")
        find.setObjectName("secondaryButton")
        find.setMinimumWidth(104)
        find.clicked.connect(self.find_book)
        search_layout.addWidget(find)
        download_layout.addWidget(search_card)

        details_card = QFrame()
        details_card.setObjectName("card")
        details_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        details_card.setMaximumHeight(310)
        details_layout = QHBoxLayout(details_card)
        details_layout.setContentsMargins(18, 18, 18, 18)
        details_layout.setSpacing(22)

        cover_column = QVBoxLayout()
        cover_column.setSpacing(9)
        cover_column.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.cover = QLabel("Обложка\nпоявится после поиска")
        self.cover.setObjectName("coverPlaceholder")
        self.cover.setFixedSize(142, 198)
        self.cover.setWordWrap(True)
        self.cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cover_column.addWidget(self.cover, 0, Qt.AlignmentFlag.AlignHCenter)
        cover_note = QLabel("EPUB · TXT · HTML")
        cover_note.setObjectName("formatBadge")
        cover_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cover_column.addWidget(cover_note)
        details_layout.addLayout(cover_column)

        options = QVBoxLayout()
        options.setSpacing(13)
        self.title_label = QLabel("Выберите произведение")
        self.title_label.setObjectName("bookTitle")
        self.title_label.setWordWrap(True)
        options.addWidget(self.title_label)

        fields = QGridLayout()
        fields.setHorizontalSpacing(12)
        fields.setVerticalSpacing(7)
        fields.setColumnStretch(0, 1)
        fields.setColumnStretch(1, 1)

        translation_label = QLabel("Перевод")
        translation_label.setObjectName("fieldLabel")
        self.translation = QComboBox()
        self.translation.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.translation.currentIndexChanged.connect(self.translation_changed)
        fields.addWidget(translation_label, 0, 0, 1, 2)
        fields.addWidget(self.translation, 1, 0, 1, 2)

        scope_label = QLabel("Главы")
        scope_label.setObjectName("fieldLabel")
        format_label = QLabel("Формат")
        format_label.setObjectName("fieldLabel")
        self.scope = QComboBox()
        self.scope.addItems(["Все главы", "Первые 10", "Последние 10", "Диапазон"])
        self.scope.currentIndexChanged.connect(self.update_scope)
        self.fmt = QComboBox()
        self.fmt.addItems(["epub", "txt", "html"])
        fields.addWidget(scope_label, 2, 0)
        fields.addWidget(format_label, 2, 1)
        fields.addWidget(self.scope, 3, 0)
        fields.addWidget(self.fmt, 3, 1)

        range_label = QLabel("Диапазон")
        range_label.setObjectName("fieldLabel")
        range_row = QHBoxLayout()
        range_row.setSpacing(8)
        self.start = QComboBox()
        self.end = QComboBox()
        range_row.addWidget(self.start)
        range_separator = QLabel("—")
        range_separator.setObjectName("mutedText")
        range_row.addWidget(range_separator)
        range_row.addWidget(self.end)
        fields.addWidget(range_label, 4, 0, 1, 2)
        fields.addLayout(range_row, 5, 0, 1, 2)
        options.addLayout(fields)

        self.add_button = QPushButton("В очередь")
        self.add_button.setObjectName("primaryButton")
        self.add_button.setMinimumHeight(42)
        self.add_button.clicked.connect(self.enqueue)
        options.addWidget(self.add_button)
        details_layout.addLayout(options, 1)
        download_layout.addWidget(details_card)

        status_card = QFrame()
        status_card.setObjectName("statusCard")
        status_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(16, 12, 16, 12)
        status_layout.setSpacing(7)
        status_header = QHBoxLayout()
        status_title = QLabel("Состояние")
        status_title.setObjectName("fieldLabel")
        self.queue_status = QLabel("Очередь пуста")
        self.queue_status.setObjectName("mutedText")
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.status = QLabel("Готово")
        self.status.setObjectName("statusText")
        status_header.addWidget(status_title)
        status_header.addWidget(self.queue_status)
        status_header.addStretch()
        status_header.addWidget(self.status)
        self.cancel_button = QPushButton("Отменить загрузку")
        self.cancel_button.setObjectName("compactButton")
        self.cancel_button.clicked.connect(self.cancel_current)
        self.clear_queue_button = QPushButton("Очистить ожидающие")
        self.clear_queue_button.setObjectName("compactButton")
        self.clear_queue_button.clicked.connect(self.clear_pending)
        status_header.addWidget(self.cancel_button)
        status_header.addWidget(self.clear_queue_button)
        status_layout.addLayout(status_header)
        status_layout.addWidget(self.progress)
        download_layout.addWidget(status_card)
        download_layout.addStretch(1)
        self.tabs.addTab(download, "Скачать")

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
        current_version = importlib.metadata.version("ranobe-downloader")
        link = QLabel(f'Версия {current_version} · <a href="{GITHUB}">GitHub SayatYuss</a>')
        link.setOpenExternalLinks(True)
        settings_form.addRow("О программе", link)
        self.check_updates_button = QPushButton("Проверить обновления")
        self.check_updates_button.clicked.connect(
            lambda: self.run_task(
                check_latest_release,
                current_version,
                on_done=lambda release: self.show_update(release, show_latest=True),
                on_failure=lambda error: log.warning(
                    "Update check failed: %s", error
                ),
                busy=False,
            )
        )
        settings_form.addRow("Обновления", self.check_updates_button)
        log_button = QPushButton("Открыть журнал")
        log_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.store.root / "desktop.log"))))
        settings_form.addRow("Диагностика", log_button)
        self.tabs.addTab(settings_page, "Настройки")

        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(QIcon("docs-site/assets/favicon.svg"))
        self.tray.setToolTip("Ranobe Downloader")
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
        self.update_queue()
        if self.token_store.load():
            self.run_task(verify_token, self.token_store.load(), on_done=self.set_user, busy=False)
        
        
        if check_update_on_startup:
            self.run_task(
                check_latest_release,
                current_version,
                on_done=self.show_update,
                on_failure=lambda error: log.warning(
                    "Update check failed: %s", error
                ),
                busy=False,
            )

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
        cover_loaded = False
        if cover:
            pixmap = QPixmap()
            if pixmap.loadFromData(cover):
                self.cover.setPixmap(pixmap.scaled(self.cover.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                cover_loaded = True
        if not cover_loaded:
            self.cover.setText("Обложка\nнедоступна")
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
        waiting = len(self.pending)
        if self.current:
            title = self.current[0].title
            suffix = f" · ожидают: {waiting}" if waiting else ""
            self.queue_status.setText(f"Скачивается: {title}{suffix}")
        elif waiting:
            self.queue_status.setText(f"Ожидают загрузки: {waiting}")
        else:
            self.queue_status.setText("Очередь пуста")
        self.cancel_button.setEnabled(self.current_task is not None)
        self.clear_queue_button.setEnabled(bool(self.pending))
        self.add_button.setText("Добавить в очередь" if self.running else "Скачать")

    def clear_pending(self):
        self.pending.clear()
        self.update_queue()

    def cancel_current(self):
        if self.current_task:
            self.current_task.cancel.set()
            self.status.setText("Отмена после текущей операции…")
            self.queue_status.setText("Текущая загрузка отменяется…")
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
        
    def show_update(self, release, show_latest: bool = False):
        if not release:
            if show_latest:
                QMessageBox.information(
                    self,
                    "Обновления",
                    "Установлена последняя версия."
                )
            return

        version = html.escape(release["version"])
        notes = html.escape(release["notes"]).replace("\n", "<br>")

        message = f"""
        <h3>Доступна новая версия {version}</h3>
        <p>Что нового:</p>
        {notes}
        <br>
        <p>
            <a href="{html.escape(release['url'], quote=True)}">
                Посмотреть полный список изменений
            </a>
        </p>
        <br>
        Открыть страницу загрузки?
        """

        answer = QMessageBox.question(
            self,
            "Доступно обновление",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )

        if answer == QMessageBox.StandardButton.Yes:
            QDesktopServices.openUrl(QUrl(release["url"]))

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

