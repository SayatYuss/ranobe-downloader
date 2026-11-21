"""Small reusable widgets used by the desktop pages."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QLabel, QPushButton, QWidget


class CoverLabel(QLabel):
    """Book cover that opens a larger preview when an image is available."""

    clicked = Signal()

    def mousePressEvent(self, event):
        pixmap = self.pixmap()
        if event.button() == Qt.MouseButton.LeftButton and pixmap is not None and not pixmap.isNull():
            self.clicked.emit()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        pixmap = self.pixmap()
        if (
            event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space)
            and pixmap is not None
            and not pixmap.isNull()
        ):
            self.clicked.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class FormatSelector(QWidget):
    """Exclusive format buttons exposing the small combo-box API used by the page."""

    FORMATS = ("epub", "txt", "html")

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons = []
        for index, value in enumerate(self.FORMATS):
            button = QPushButton(value.upper())
            button.setObjectName("formatButton")
            button.setCheckable(True)
            button.setAccessibleName(f"Формат {value.upper()}")
            self.group.addButton(button, index)
            self.buttons.append(button)
            layout.addWidget(button, 1)
        self.buttons[0].setChecked(True)

    def currentText(self):
        checked = self.group.checkedId()
        return self.FORMATS[checked] if checked >= 0 else self.FORMATS[0]

    def currentIndex(self):
        checked = self.group.checkedId()
        return checked if checked >= 0 else 0

    def findText(self, value):
        try:
            return self.FORMATS.index(str(value).lower())
        except ValueError:
            return -1

    def setCurrentIndex(self, index):
        if 0 <= index < len(self.buttons):
            self.buttons[index].setChecked(True)
