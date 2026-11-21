"""Small reusable widgets used by the desktop pages."""
from __future__ import annotations

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton, QWidget


class Toast(QFrame):
    """Short, non-modal notification displayed over the current window."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("toast")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumWidth(260)
        self.setMaximumWidth(440)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 11, 14, 11)
        self.label = QLabel()
        self.label.setWordWrap(True)
        layout.addWidget(self.label)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)
        self.hide()

    def show_message(self, message, timeout=3500):
        self.label.setText(message)
        self.adjustSize()
        self.reposition()
        self.show()
        self.raise_()
        self.timer.start(timeout)

    def reposition(self):
        if self.parentWidget() is None:
            return
        margin = 20
        x = max(margin, self.parentWidget().width() - self.width() - margin)
        y = max(margin, self.parentWidget().height() - self.height() - margin)
        self.move(x, y)


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
