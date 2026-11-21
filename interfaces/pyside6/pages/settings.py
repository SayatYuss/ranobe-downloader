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
        cache_path = QLabel(str(self.store.cache))
        cache_path.setObjectName("mutedText")
        cache_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        cache_info.addWidget(cache_label)
        cache_info.addWidget(cache_path)
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
        token_label = QLabel("Bearer-токен RanobeLib")
        token_label.setObjectName("fieldLabel")
        account.addWidget(token_label)
        self.token_input = QLineEdit()
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_input.setPlaceholderText("Bearer token")
        self.token_input.returnPressed.connect(self.login)
        account.addWidget(self.token_input)
        auth_actions = QHBoxLayout()
        auth_actions.addStretch()
        connect = QPushButton("Войти")
        connect.setObjectName("primaryButton")
        connect.clicked.connect(self.login)
        logout = QPushButton("Выйти")
        logout.clicked.connect(self.logout)
        auth_actions.addWidget(connect)
        auth_actions.addWidget(logout)
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
                QMessageBox.information(self, "Обновления", "Установлена последняя версия.")
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
