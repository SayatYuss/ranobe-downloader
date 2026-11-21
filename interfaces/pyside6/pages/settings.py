"""Settings page: storage, appearance, authentication and diagnostics."""
from __future__ import annotations

import html
import importlib.metadata
import logging
import shutil

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from interfaces.pyside6.tasks import check_latest_release, verify_token
from interfaces.pyside6.theme import apply_theme

log = logging.getLogger(__name__)
GITHUB = "https://github.com/SayatYuss"


class SettingsPageMixin:
    """UI and behavior for persistent desktop preferences."""

    def build_settings_page(self):
        page = QWidget()
        page.setObjectName("settingsPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 18, 8, 8)
        layout.setSpacing(14)

        title = QLabel("Настройки")
        title.setObjectName("pageTitle")
        hint = QLabel("Управляйте сохранением книг, оформлением, авторизацией и обслуживанием приложения.")
        hint.setObjectName("mutedText")
        hint.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(hint)

        self.settings_scroll = QScrollArea()
        self.settings_scroll.setObjectName("settingsScroll")
        self.settings_scroll.setWidgetResizable(True)
        self.settings_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.settings_scroll.viewport().setAutoFillBackground(False)
        content = QWidget()
        content.setObjectName("settingsContent")
        cards = QVBoxLayout(content)
        cards.setContentsMargins(0, 0, 6, 0)
        cards.setSpacing(12)
        self.settings_cards = []

        def create_card(card_title, description):
            card = QFrame()
            card.setObjectName("card")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(18, 16, 18, 16)
            card_layout.setSpacing(10)
            heading = QLabel(card_title)
            heading.setObjectName("sectionTitle")
            note = QLabel(description)
            note.setObjectName("mutedText")
            note.setWordWrap(True)
            card_layout.addWidget(heading)
            card_layout.addWidget(note)
            self.settings_cards.append(card)
            cards.addWidget(card)
            return card_layout

        downloads = create_card(
            "Загрузки",
            "Выберите папку для готовых книг и управляйте временными файлами.",
        )
        directory_label = QLabel("Папка загрузок")
        directory_label.setObjectName("fieldLabel")
        downloads.addWidget(directory_label)
        self.directory = QLineEdit(self.store.settings.get("directory", ""))
        self.directory.editingFinished.connect(self.save_dir)
        browse = QPushButton("Обзор…")
        browse.clicked.connect(self.choose_dir)
        directory_row = QHBoxLayout()
        directory_row.addWidget(self.directory)
        directory_row.addWidget(browse)
        downloads.addLayout(directory_row)

        cache_row = QHBoxLayout()
        cache_info = QVBoxLayout()
        cache_info.setSpacing(2)
        cache_label = QLabel("Кеш глав и изображений")
        cache_label.setObjectName("fieldLabel")
        self.cache_path_label = QLabel(str(self.store.cache))
        self.cache_path_label.setObjectName("mutedText")
        self.cache_path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.cache_size_label = QLabel()
        self.cache_size_label.setObjectName("statusText")
        cache_info.addWidget(cache_label)
        cache_info.addWidget(self.cache_path_label)
        cache_info.addWidget(self.cache_size_label)
        cache_row.addLayout(cache_info, 1)
        clear = QPushButton("Очистить кеш")
        clear.clicked.connect(self.clear_cache)
        cache_row.addWidget(clear)
        downloads.addLayout(cache_row)

        appearance = create_card(
            "Оформление",
            "Системная тема автоматически следует настройкам операционной системы.",
        )
        appearance_row = QHBoxLayout()
        theme_label = QLabel("Тема приложения")
        theme_label.setObjectName("fieldLabel")
        appearance_row.addWidget(theme_label)
        appearance_row.addStretch()
        self.theme_box = QComboBox()
        self.theme_box.addItems(["Системная", "Светлая", "Тёмная"])
        self.theme_box.setMinimumWidth(200)
        self.theme_box.setCurrentIndex(
            {"system": 0, "light": 1, "dark": 2}.get(
                self.store.settings.get("theme", "system"), 0
            )
        )
        self.theme_box.currentIndexChanged.connect(self.change_theme)
        appearance_row.addWidget(self.theme_box)
        appearance.addLayout(appearance_row)

        account = create_card(
            "Авторизация",
            "Токен сохраняется в системном хранилище учётных данных и нужен только для доступных вам материалов.",
        )
        self.auth_status = QLabel("Не авторизован")
        self.auth_status.setObjectName("authStatus")
        account.addWidget(self.auth_status)
        self.token_entry = QWidget()
        token_entry_layout = QVBoxLayout(self.token_entry)
        token_entry_layout.setContentsMargins(0, 0, 0, 0)
        token_entry_layout.setSpacing(6)
        token_label = QLabel("Bearer-токен RanobeLib")
        token_label.setObjectName("fieldLabel")
        token_entry_layout.addWidget(token_label)
        self.token_input = QLineEdit()
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_input.setPlaceholderText("Bearer token")
        self.token_input.returnPressed.connect(self.login)
        token_entry_layout.addWidget(self.token_input)
        account.addWidget(self.token_entry)
        auth_actions = QHBoxLayout()
        auth_actions.addStretch()
        self.login_button = QPushButton("Войти")
        self.login_button.setObjectName("primaryButton")
        self.login_button.clicked.connect(self.login)
        self.logout_button = QPushButton("Выйти")
        self.logout_button.clicked.connect(self.logout)
        auth_actions.addWidget(self.login_button)
        auth_actions.addWidget(self.logout_button)
        account.addLayout(auth_actions)

        application = create_card(
            "Приложение",
            "Проверяйте обновления и открывайте журнал при диагностике проблем.",
        )
        self.current_version = importlib.metadata.version("ranobe-downloader")
        link = QLabel(f'Версия {self.current_version} · <a href="{GITHUB}">GitHub SayatYuss</a>')
        link.setOpenExternalLinks(True)
        application.addWidget(link)
        application_actions = QHBoxLayout()
        application_actions.addStretch()
        self.check_updates_button = QPushButton("Проверить обновления")
        self.check_updates_button.clicked.connect(self.check_updates)
        application_actions.addWidget(self.check_updates_button)
        log_button = QPushButton("Открыть журнал")
        log_button.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(self.store.root / "desktop.log"))
            )
        )
        application_actions.addWidget(log_button)
        application.addLayout(application_actions)

        cards.addStretch(1)
        self.settings_scroll.setWidget(content)
        layout.addWidget(self.settings_scroll, 1)
        self.tabs.addTab(page, "Настройки")
        self.settings_page = page
        self.tabs.currentChanged.connect(self._settings_tab_changed)
        self.refresh_cache_size()
        self.set_auth_state()

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
            self.show_toast("Кеш можно очистить после завершения загрузок")
            return
        shutil.rmtree(self.store.cache, ignore_errors=True)
        self.store.cache.mkdir(exist_ok=True)
        self.refresh_cache_size()
        self.show_toast("Кеш очищен")

    @staticmethod
    def format_size(size):
        value = float(size)
        for unit in ("B", "KiB", "MiB", "GiB"):
            if value < 1024 or unit == "GiB":
                return f"{value:.0f} {unit}" if unit in ("B", "KiB") else f"{value:.1f} {unit}"
            value /= 1024

    def refresh_cache_size(self):
        total = 0
        try:
            for path in self.store.cache.rglob("*"):
                if path.is_file():
                    try:
                        total += path.stat().st_size
                    except OSError:
                        continue
        except OSError:
            pass
        self.cache_size_label.setText(f"Использовано: {self.format_size(total)}")

    def _settings_tab_changed(self, index):
        if self.tabs.widget(index) is self.settings_page:
            self.refresh_cache_size()

    def set_auth_state(self, username=None, pending=False):
        if pending:
            self.auth_status.setText("Проверка авторизации…")
            self.token_entry.hide()
            self.login_button.hide()
            self.logout_button.hide()
            return
        if username:
            self.auth_status.setText(f"Авторизован: {username}")
            self.token_entry.hide()
            self.login_button.hide()
            self.logout_button.show()
        else:
            self.auth_status.setText("Не авторизован")
            self.token_entry.show()
            self.login_button.show()
            self.logout_button.hide()

    def set_user(self, username):
        self.username.setText(username)
        self.token_input.clear()
        self.set_auth_state(username)

    def login(self):
        token = self.token_input.text().strip()
        if token.lower().startswith("bearer "):
            token = token[7:].strip()
        if not token:
            return

        self.set_auth_state(pending=True)

        def success(username):
            self.token_store.save(token)
            self.set_user(username)
            self.show_toast(f"Выполнен вход: {username}")

        self.run_task(verify_token, token, on_done=success, on_failure=self.auth_failed)

    def auth_failed(self, message):
        self.set_auth_state()
        self.report_error(message)

    def logout(self):
        self.token_store.delete()
        self.username.setText("Не авторизован")
        self.token_input.clear()
        self.set_auth_state()
        self.show_toast("Вы вышли из учётной записи")

    def check_updates(self):
        self.run_task(
            check_latest_release,
            self.current_version,
            on_done=lambda release: self.show_update(release, show_latest=True),
            on_failure=lambda error: log.warning("Update check failed: %s", error),
            busy=False,
        )

    def show_update(self, release, show_latest=False):
        if not release:
            if show_latest:
                self.show_toast("Установлена последняя версия")
            return
        version = html.escape(release["version"])
        notes = html.escape(release["notes"]).replace("\n", "<br>")
        message = f"""
        <h3>Доступна новая версия {version}</h3>
        <p>Что нового:</p>
        {notes}
        <br>
        <p><a href="{html.escape(release['url'], quote=True)}">Посмотреть полный список изменений</a></p>
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
