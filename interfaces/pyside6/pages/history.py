"""History page: filtering, completed-file actions and presentation."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class HistoryPageMixin:
    """UI and behavior for persistent completed downloads."""

    def build_history_page(self):
        page = QWidget()
        page.setObjectName("historyPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 18, 8, 8)
        layout.setSpacing(14)

        title = QLabel("История загрузок")
        title.setObjectName("pageTitle")
        hint = QLabel("Здесь хранятся готовые книги. Выберите запись, чтобы открыть или скачать её снова.")
        hint.setObjectName("mutedText")
        hint.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(hint)

        search_card = QFrame()
        search_card.setObjectName("card")
        search_layout = QHBoxLayout(search_card)
        search_layout.setContentsMargins(16, 14, 16, 14)
        search_layout.setSpacing(10)
        self.history_filter = QLineEdit()
        self.history_filter.setPlaceholderText("Поиск по названию или формату")
        self.history_filter.setClearButtonEnabled(True)
        self.history_filter.textChanged.connect(self.reload_history)
        search_layout.addWidget(self.history_filter, 1)
        self.history_count = QLabel("0 файлов")
        self.history_count.setObjectName("accountBadge")
        search_layout.addWidget(self.history_count)
        layout.addWidget(search_card)

        table_card = QFrame()
        table_card.setObjectName("card")
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(1, 1, 1, 1)
        table_layout.setSpacing(0)

        self.history_empty = QWidget()
        empty_layout = QVBoxLayout(self.history_empty)
        empty_layout.setContentsMargins(24, 48, 24, 48)
        empty_layout.setSpacing(7)
        empty_layout.addStretch()
        self.history_empty_title = QLabel("История пока пуста")
        self.history_empty_title.setObjectName("emptyTitle")
        self.history_empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.history_empty_hint = QLabel("Скачанные книги появятся здесь автоматически.")
        self.history_empty_hint.setObjectName("mutedText")
        self.history_empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.history_empty_hint.setWordWrap(True)
        empty_layout.addWidget(self.history_empty_title)
        empty_layout.addWidget(self.history_empty_hint)
        empty_layout.addStretch()
        table_layout.addWidget(self.history_empty, 1)

        self.history = QTableWidget(0, 4)
        self.history.setHorizontalHeaderLabels(["Название", "Формат", "Дата", "Размер"])
        header = self.history.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.history.verticalHeader().setVisible(False)
        self.history.setShowGrid(False)
        self.history.setAlternatingRowColors(True)
        self.history.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.history.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.history.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.history.cellDoubleClicked.connect(self.open_history)
        self.history.itemSelectionChanged.connect(self.update_history_actions)
        table_layout.addWidget(self.history, 1)
        layout.addWidget(table_card, 1)

        self.history_actions = QFrame()
        self.history_actions.setObjectName("statusCard")
        actions = QHBoxLayout(self.history_actions)
        actions.setContentsMargins(12, 9, 12, 9)
        actions.setSpacing(8)
        selected_hint = QLabel("Выбрана книга")
        selected_hint.setObjectName("mutedText")
        actions.addWidget(selected_hint)
        actions.addStretch()
        self.history_open_button = QPushButton("Открыть")
        self.history_open_button.setObjectName("primaryButton")
        self.history_open_button.clicked.connect(self.open_selected_history)
        actions.addWidget(self.history_open_button)
        self.history_folder_button = QPushButton("Показать в папке")
        self.history_folder_button.clicked.connect(self.open_history_folder)
        actions.addWidget(self.history_folder_button)
        self.history_repeat_button = QPushButton("Скачать снова")
        self.history_repeat_button.clicked.connect(self.redownload_history)
        actions.addWidget(self.history_repeat_button)
        self.history_delete_button = QPushButton("Удалить из истории")
        self.history_delete_button.setObjectName("dangerButton")
        self.history_delete_button.clicked.connect(self.delete_history_record)
        actions.addWidget(self.history_delete_button)
        self.history_actions.hide()
        layout.addWidget(self.history_actions)
        self.tabs.addTab(page, "История")

    @staticmethod
    def history_count_text(count):
        tail = count % 100
        if 11 <= tail <= 14:
            word = "файлов"
        elif count % 10 == 1:
            word = "файл"
        elif count % 10 in (2, 3, 4):
            word = "файла"
        else:
            word = "файлов"
        return f"{count} {word}"

    def update_history_actions(self):
        self.history_actions.setVisible(self.selected_history_index() is not None)

    def reload_history(self):
        query = self.history_filter.text().strip().casefold()
        self.history_indices = [
            index
            for index, item in enumerate(self.store.history)
            if query in item.get("title", "").casefold()
            or query in item.get("format", "").casefold()
        ]
        self.history.clearSelection()
        self.history.setCurrentCell(-1, -1)
        self.history.setRowCount(len(self.history_indices))
        for row, index in enumerate(self.history_indices):
            record = self.store.history[index]
            for column, key in enumerate(("title", "format", "date", "size")):
                value = self._history_value(record, key)
                item = QTableWidgetItem(str(value))
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, record.get("path"))
                    item.setToolTip(str(record.get("path", "")))
                elif column in (1, 2):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                elif column == 3:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if key == "format":
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                self.history.setItem(row, column, item)
            self.history.setRowHeight(row, 44)

        count = len(self.history_indices)
        self.history_count.setText(self.history_count_text(count))
        self.history.setVisible(bool(count))
        self.history_empty.setVisible(not count)
        if not count and query and self.store.history:
            self.history_empty_title.setText("Ничего не найдено")
            self.history_empty_hint.setText("Попробуйте изменить поисковый запрос.")
        else:
            self.history_empty_title.setText("История пока пуста")
            self.history_empty_hint.setText("Скачанные книги появятся здесь автоматически.")
        self.update_history_actions()

    @staticmethod
    def _history_value(record, key):
        value = record.get(key, "")
        if key == "size":
            size = int(value or 0)
            return f"{size / 1048576:.1f} MiB" if size >= 1048576 else f"{size / 1024:.0f} KiB"
        if key == "date" and value:
            try:
                return datetime.fromisoformat(str(value)).strftime("%d.%m.%Y · %H:%M")
            except ValueError:
                return value
        if key == "format":
            return str(value).upper()
        return value

    def open_history(self, row, _column):
        item = self.history.item(row, 0)
        if not item:
            return
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
        if index is None:
            return
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
        if index is None:
            return
        record = self.store.history[index]
        reference = record.get("reference")
        if not reference:
            QMessageBox.information(
                self,
                "Повторить",
                "Для старой записи не сохранена ссылка на произведение.",
            )
            return
        self.repeat_record = dict(record)
        self.reference.setText(reference)
        self.tabs.setCurrentIndex(0)
        self.find_book()
