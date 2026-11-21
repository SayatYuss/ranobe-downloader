"""Desktop application composition, worker-thread dispatch and lifecycle."""
from __future__ import annotations

import logging
import sys
from collections import deque

from PySide6.QtCore import QThread, Slot
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSystemTrayIcon,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.auth.storage import KeyringTokenStorage
from interfaces.pyside6.pages.download import DownloadPageMixin
from interfaces.pyside6.pages.history import HistoryPageMixin
from interfaces.pyside6.pages.settings import SettingsPageMixin
from interfaces.pyside6.storage import Store, configure_logging
from interfaces.pyside6.tasks import (
    DownloadCancelled,
    Task,
    check_latest_release,
    lookup_book,
    perform_download,
    verify_token,
)
from interfaces.pyside6.theme import apply_theme
from interfaces.pyside6.widgets import CoverLabel, FormatSelector

log = logging.getLogger(__name__)
__all__ = [
    "Window", "main", "lookup", "perform_download", "DownloadCancelled",
    "CoverLabel", "FormatSelector",
]

# Backward-compatible names for callers that imported these from app.py.
lookup = lookup_book


class Window(DownloadPageMixin, HistoryPageMixin, SettingsPageMixin, QMainWindow):
    """Top-level window coordinating independent pages and shared application state."""

    def __init__(self, check_update_on_startup=True):
        super().__init__()
        self.store = Store()
        configure_logging(self.store.root)
        self.token_store = KeyringTokenStorage()

        # Shared page state.
        self.book = None
        self.cover_pixmap = None
        self.cover_available = False
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

        # Worker and lifecycle state.
        self.threads = []
        self.tasks = []
        self.exiting = False

        self.setWindowTitle("Ranobe Downloader")
        self.resize(980, 700)
        self.setMinimumSize(840, 700)
        self.setAcceptDrops(True)
        self._build_shell()
        self.build_download_page()
        self.build_history_page()
        self.build_settings_page()
        self._build_tray()
        self._initialize_pages(check_update_on_startup)

    def _build_shell(self):
        wrapper = QWidget()
        wrapper.setObjectName("appShell")
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(18)

        header = QHBoxLayout()
        header.setSpacing(12)
        brand = QVBoxLayout()
        brand.setSpacing(1)
        title = QLabel("Ranobe Downloader")
        title.setObjectName("brandTitle")
        subtitle = QLabel("Личная библиотека — в удобном формате")
        subtitle.setObjectName("mutedText")
        brand.addWidget(title)
        brand.addWidget(subtitle)
        header.addLayout(brand)
        header.addStretch()
        self.username = QLabel("Не авторизован")
        self.username.setObjectName("accountBadge")
        header.addWidget(self.username)
        layout.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        layout.addWidget(self.tabs)
        self.setCentralWidget(wrapper)

    def _build_tray(self):
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

    def _initialize_pages(self, check_update_on_startup):
        self.reload_history()
        self.update_scope()
        self.update_queue()
        self.set_book_controls_enabled(False)
        token = self.token_store.load()
        if token:
            self.run_task(verify_token, token, on_done=self.set_user, busy=False)
        if check_update_on_startup:
            self.run_task(
                check_latest_release,
                self.current_version,
                on_done=self.show_update,
                on_failure=lambda error: log.warning("Update check failed: %s", error),
                busy=False,
            )

    def run_task(self, operation, *args, on_done, busy=True, on_failure=None):
        """Run a blocking operation and deliver its result on the GUI thread."""
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
            task.progress.connect(self.on_progress)
        self.tasks.append(task)
        thread.finished.connect(
            lambda: self.threads.remove(thread) if thread in self.threads else None
        )
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
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
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
            QMessageBox.information(
                self,
                "Загрузка",
                "Дождитесь завершения фоновых операций",
            )
            event.ignore()
        else:
            event.accept()

    def quit_app(self):
        if self.running or self.pending or self.threads:
            QMessageBox.information(
                self,
                "Загрузка",
                "Дождитесь завершения фоновых операций",
            )
            return
        self.exiting = True
        self.tray.hide()
        QApplication.quit()


def main():
    if "--check" in sys.argv:
        import PySide6  # noqa: F401
        from ranobe_downloader import Downloader  # noqa: F401

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
