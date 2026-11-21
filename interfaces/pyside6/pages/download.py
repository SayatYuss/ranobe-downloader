"""Download page: book lookup, selection, queue, progress and cover preview."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from interfaces.pyside6.tasks import lookup_book, perform_download
from interfaces.pyside6.widgets import CoverLabel, FormatSelector


class DownloadPageMixin:
    """UI and behavior belonging to the download workflow."""

    def build_download_page(self):
        page = QWidget()
        page.setObjectName("downloadPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 18, 8, 8)
        layout.setSpacing(14)

        title = QLabel("Скачать произведение")
        title.setObjectName("pageTitle")
        hint = QLabel("Вставьте ссылку с RanobeLib — перевод, главы и обложка загрузятся автоматически.")
        hint.setObjectName("mutedText")
        hint.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(hint)

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
        self.lookup_progress = QProgressBar()
        self.lookup_progress.setRange(0, 0)
        self.lookup_progress.setTextVisible(False)
        self.lookup_progress.setFixedSize(48, 7)
        self.lookup_progress.hide()
        search_layout.addWidget(self.lookup_progress)
        self.find_button = QPushButton("Найти")
        self.find_button.setObjectName("secondaryButton")
        self.find_button.setMinimumWidth(104)
        self.find_button.clicked.connect(self.find_book)
        search_layout.addWidget(self.find_button)
        layout.addWidget(search_card)

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
        self.cover = CoverLabel("Обложка\nпоявится после поиска")
        self.cover.setObjectName("coverPlaceholder")
        self.cover.setFixedSize(142, 198)
        self.cover.setWordWrap(True)
        self.cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.cover.setAccessibleName("Обложка произведения")
        self.cover.clicked.connect(self.show_cover_preview)
        cover_column.addWidget(self.cover, 0, Qt.AlignmentFlag.AlignHCenter)
        cover_note = QLabel("EPUB · TXT · HTML")
        cover_note.setObjectName("formatBadge")
        cover_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cover_column.addWidget(cover_note)
        details_layout.addLayout(cover_column)

        options = QVBoxLayout()
        options.setSpacing(7)
        self.title_label = QLabel("Выберите произведение")
        self.title_label.setObjectName("bookTitle")
        self.title_label.setWordWrap(True)
        options.addWidget(self.title_label)
        self.book_details = QLabel()
        self.book_details.setObjectName("bookMeta")
        self.book_details.setWordWrap(True)
        self.book_details.hide()
        options.addWidget(self.book_details)

        fields = QGridLayout()
        fields.setHorizontalSpacing(12)
        fields.setVerticalSpacing(4)
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
        self.fmt = FormatSelector()
        fields.addWidget(scope_label, 2, 0)
        fields.addWidget(format_label, 2, 1)
        fields.addWidget(self.scope, 3, 0)
        fields.addWidget(self.fmt, 3, 1)

        range_label = QLabel("Диапазон")
        range_label.setObjectName("fieldLabel")
        range_layout = QHBoxLayout()
        range_layout.setSpacing(8)
        self.start = QComboBox()
        self.end = QComboBox()
        range_layout.addWidget(self.start)
        separator = QLabel("—")
        separator.setObjectName("mutedText")
        range_layout.addWidget(separator)
        range_layout.addWidget(self.end)
        fields.addWidget(range_label, 4, 0, 1, 2)
        fields.addLayout(range_layout, 5, 0, 1, 2)
        options.addLayout(fields)

        self.add_button = QPushButton("В очередь")
        self.add_button.setObjectName("primaryButton")
        self.add_button.setMinimumHeight(42)
        self.add_button.clicked.connect(self.enqueue)
        options.addWidget(self.add_button)
        details_layout.addLayout(options, 1)
        layout.addWidget(details_card)

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
        layout.addWidget(status_card)
        layout.addStretch(1)
        self.tabs.addTab(page, "Скачать")

    def set_book_controls_enabled(self, enabled):
        for widget in (self.translation, self.scope, self.fmt, self.add_button):
            widget.setEnabled(enabled)
        self.update_scope()

    def set_lookup_busy(self, busy):
        self.lookup_pending = busy
        self.find_button.setEnabled(not busy)
        self.find_button.setText("Поиск…" if busy else "Найти")
        self.lookup_progress.setVisible(busy)
        self.set_book_controls_enabled(not busy and self.book is not None)

    def find_book(self):
        reference = self.reference.text().strip()
        if not reference or self.lookup_pending:
            return
        self.set_lookup_busy(True)
        self.status.setText("Загрузка данных…")
        self.run_task(
            lookup_book,
            reference,
            self.token_store.load(),
            on_done=self.book_loaded,
            on_failure=self.lookup_failed,
        )

    def lookup_failed(self, message):
        self.set_lookup_busy(False)
        self.repeat_record = None
        self.report_error(message)

    def book_loaded(self, result):
        self.book, cover = result
        self.set_lookup_busy(False)
        self.scope.setCurrentIndex(0)
        self.title_label.setText(self.book.title)
        self.cover_pixmap = None
        self.cover_available = False
        self.cover.clear()
        if cover:
            pixmap = QPixmap()
            if pixmap.loadFromData(cover):
                self.cover_pixmap = pixmap
                self.cover.setPixmap(pixmap.scaled(
                    self.cover.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ))
                self.cover.setObjectName("coverPreview")
                self.cover.setCursor(Qt.CursorShape.PointingHandCursor)
                self.cover.setToolTip("Нажмите, чтобы увеличить обложку")
                self.cover_available = True
        if not self.cover_available:
            self.cover.setObjectName("coverPlaceholder")
            self.cover.unsetCursor()
            self.cover.setToolTip("")
            self.cover.setText("Обложка\nнедоступна")
        self.cover.style().unpolish(self.cover)
        self.cover.style().polish(self.cover)

        self.translation.blockSignals(True)
        self.translation.clear()
        self.translation_ids = [item.branch_id for item in self.book.translations]
        for item in self.book.translations:
            self.translation.addItem(f"{item.name or 'Перевод'} ({item.chapter_count})")
        if not self.translation_ids:
            self.translation_ids = [None]
            self.translation.addItem("Без выбора перевода")
        self.translation.blockSignals(False)
        self.translation_changed()
        self.book_details.show()
        self.update_book_details()
        self.status.setText("Готово")
        if self.repeat_record is not None:
            self.apply_repeat_selection()

    def show_cover_preview(self):
        if self.cover_pixmap is None or self.cover_pixmap.isNull():
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Обложка — {self.book.title if self.book else 'Ranobe Downloader'}")
        dialog.setModal(True)
        dialog_layout = QVBoxLayout(dialog)
        dialog_layout.setContentsMargins(18, 18, 18, 18)
        dialog_layout.setSpacing(12)
        preview = QLabel()
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        available = self.screen().availableGeometry()
        preview.setPixmap(self.cover_pixmap.scaled(
            min(560, round(available.width() * 0.7)),
            min(720, round(available.height() * 0.75)),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))
        dialog_layout.addWidget(preview)
        close = QPushButton("Закрыть")
        close.clicked.connect(dialog.accept)
        dialog_layout.addWidget(close, 0, Qt.AlignmentFlag.AlignRight)
        dialog.exec()

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
                self.start.setCurrentIndex(self.start.findData(start))
            if end is not None:
                self.end.setCurrentIndex(self.end.findData(end))
        position = self.fmt.findText(record.get("format", "epub"))
        if position >= 0:
            self.fmt.setCurrentIndex(position)
        self.enqueue()

    def translation_changed(self):
        if not self.book:
            return
        index = self.translation.currentIndex()
        if index < 0:
            return
        self.chapters = self.book.list_chapters(self.translation_ids[index])
        for widget in (self.start, self.end):
            widget.clear()
            for chapter in self.chapters:
                widget.addItem(
                    f"Том {chapter['volume']}, глава {chapter['number']}: {chapter['name'] or ''}",
                    chapter["id"],
                )
        if self.chapters:
            self.end.setCurrentIndex(len(self.chapters) - 1)
        self.update_book_details()
        self.update_scope()

    def update_book_details(self):
        if not self.book:
            self.book_details.hide()
            return
        authors = ", ".join(getattr(self.book, "authors", ()) or ()) or "не указан"
        chapter_count = getattr(self.book, "chapter_count", len(self.chapters))
        translations = getattr(self.book, "translations", ())
        index = self.translation.currentIndex()
        if 0 <= index < len(translations):
            translation = translations[index].name or "без названия"
        else:
            translation = "единственный" if not translations else "не выбран"
        cover_status = "доступна" if self.cover_available else "недоступна"
        self.book_details.setText(
            f"Автор: {authors}  ·  Глав: {chapter_count}  ·  "
            f"Перевод: {translation}  ·  Обложка: {cover_status}"
        )
        self.book_details.setToolTip(self.book_details.text())

    def update_scope(self):
        enabled = self.book is not None and not self.lookup_pending and self.scope.currentIndex() == 3
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
            suffix = f" · ожидают: {waiting}" if waiting else ""
            self.queue_status.setText(f"Скачивается: {self.current[0].title}{suffix}")
        elif waiting:
            self.queue_status.setText(f"Ожидают загрузки: {waiting}")
        else:
            self.queue_status.setText("Очередь пуста")
        has_current = self.current_task is not None
        has_waiting = bool(self.pending)
        self.cancel_button.setVisible(has_current)
        self.cancel_button.setEnabled(has_current)
        self.clear_queue_button.setVisible(has_waiting)
        self.clear_queue_button.setEnabled(has_waiting)
        self.add_button.setText("Добавить в очередь" if self.running else "Скачать")

    def clear_pending(self):
        count = len(self.pending)
        self.pending.clear()
        self.update_queue()
        if count:
            self.show_toast(f"Удалено ожидающих загрузок: {count}")

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
            self.store.add_download(
                title=book.title,
                path=Path(saved),
                fmt=fmt,
                reference=book.slug_url,
                branch_id=branch,
                start_id=start,
                end_id=end,
            )
            self.reload_history()
            self.status.setText(f"Сохранено: {saved}")
            self.show_toast(f"Загрузка завершена: {book.title}")
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
                self.show_toast("Загрузка отменена")
            else:
                self.status.setText("Ошибка загрузки")
                QMessageBox.warning(self, "Ошибка", message)
            self.run_next()

        self.run_task(
            perform_download,
            book,
            branch,
            fmt,
            start,
            end,
            path,
            self.store.cache,
            self.token_store.load(),
            on_done=completed,
            on_failure=failed,
        )

    def on_progress(self, current, total, chapter):
        self.progress.setValue(round(current * 100 / total) if total else 0)
        self.status.setText(f"{current}/{total} — {chapter}")
