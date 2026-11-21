"""Polished neutral Qt styling with system/light/dark palette support."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

def apply_theme(app: QApplication, mode: str = "system"):
    app.setStyle("Fusion")
    app._desktop_theme_mode = mode
    if not getattr(app, "_desktop_theme_connected", False):
        app.styleHints().colorSchemeChanged.connect(
            lambda _: apply_theme(app, "system")
            if app._desktop_theme_mode == "system" else None
        )
        app._desktop_theme_connected = True
    dark = mode == "dark" or (
        mode == "system" and app.styleHints().colorScheme() == Qt.ColorScheme.Dark
    )
    base = "#111318" if dark else "#f4f6fa"
    surface = "#1a1d24" if dark else "#ffffff"
    elevated = "#222630" if dark else "#f8f9fc"
    text = "#f2f4f7" if dark else "#18202d"
    muted = "#a4a9b3" if dark else "#687080"
    outline = "#343946" if dark else "#dce1e9"
    accent = "#858bff" if dark else "#5962df"
    accent_hover = "#969bff" if dark else "#4852cf"
    accent_pressed = "#7379e8" if dark else "#3d46b8"
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(base))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(text))
    palette.setColor(QPalette.ColorRole.Base, QColor(surface))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(elevated))
    palette.setColor(QPalette.ColorRole.Text, QColor(text))
    palette.setColor(QPalette.ColorRole.Button, QColor(surface))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(text))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(accent))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(muted))
    app.setPalette(palette)
    app.setStyleSheet(STYLE + f"""
        QWidget {{ color: {text}; }}
        QMainWindow, QWidget#appShell {{ background: {base}; }}
        QScrollArea#settingsScroll, QWidget#settingsContent {{ background: transparent; border: 0; }}
        QFrame#card {{ background: {surface}; border: 1px solid {outline}; }}
        QFrame#statusCard {{ background: {elevated}; border: 1px solid {outline}; }}
        QLabel#mutedText, QLabel#fieldLabel {{ color: {muted}; }}
        QLabel#accountBadge, QLabel#formatBadge {{
            color: {muted}; background: {elevated}; border: 1px solid {outline};
        }}
        QLabel#coverPlaceholder {{
            color: {muted}; background: {elevated}; border: 1px dashed {outline};
        }}
        QLabel#coverPreview {{ background: {elevated}; border: 1px solid {outline}; }}
        QLabel#coverPreview:hover {{ border-color: {accent}; }}
        QLineEdit, QComboBox, QTableWidget, QPlainTextEdit {{
            background: {elevated}; border-color: {outline}; selection-background-color: {accent};
        }}
        QLineEdit:focus, QComboBox:focus {{ border: 2px solid {accent}; padding: 8px 10px; }}
        QPushButton {{ background: {surface}; border-color: {outline}; }}
        QPushButton:hover {{ background: {elevated}; border-color: {accent}; }}
        QPushButton#primaryButton {{ background: {accent}; color: #ffffff; border-color: {accent}; }}
        QPushButton#primaryButton:hover {{ background: {accent_hover}; border-color: {accent_hover}; }}
        QPushButton#primaryButton:pressed {{ background: {accent_pressed}; }}
        QPushButton#primaryButton:disabled {{
            background: {outline}; color: {muted}; border-color: {outline};
        }}
        QPushButton#dangerButton {{ color: {'#ff9b9b' if dark else '#b42318'}; }}
        QPushButton#dangerButton:hover {{
            background: {'#3a2024' if dark else '#fff1f0'};
            border-color: {'#8f444c' if dark else '#f1aaa5'};
        }}
        QTabBar::tab:selected {{ color: {accent}; border-bottom-color: {accent}; }}
        QProgressBar {{ background: {surface}; border-color: {outline}; }}
        QProgressBar::chunk {{ background: {accent}; }}
        QHeaderView::section {{ background: {surface}; border-bottom-color: {outline}; }}
    """)

STYLE = """
QWidget { font-size: 13px; }
QMainWindow { background: palette(window); }
QLabel#brandTitle { font-size: 18px; font-weight: 700; }
QLabel#pageTitle { font-size: 22px; font-weight: 700; }
QLabel#bookTitle { font-size: 18px; font-weight: 650; }
QLabel#sectionTitle { font-size: 16px; font-weight: 650; }
QLabel#emptyTitle { font-size: 17px; font-weight: 650; }
QLabel#fieldLabel { font-size: 11px; font-weight: 600; }
QLabel#statusText { font-weight: 600; }
QLabel#accountBadge, QLabel#formatBadge {
    border-radius: 11px; padding: 5px 10px; font-size: 11px; font-weight: 600;
}
QLabel#coverPlaceholder, QLabel#coverPreview { border-radius: 10px; padding: 12px; }
QFrame#card, QFrame#statusCard { border-radius: 12px; }
QTabWidget::pane { border: 0; }
QTabBar::tab {
    padding: 11px 18px; margin-right: 4px; border: 0;
    border-bottom: 2px solid transparent;
}
QTabBar::tab:selected { font-weight: 650; }
QLineEdit, QComboBox, QPlainTextEdit, QTableWidget {
    border: 1px solid palette(mid); border-radius: 8px; padding: 9px 11px;
}
QLineEdit, QComboBox { min-height: 20px; }
QComboBox::drop-down { border: 0; width: 24px; }
QPushButton {
    padding: 9px 16px; border: 1px solid palette(mid); border-radius: 8px;
    font-weight: 600;
}
QPushButton#compactButton { padding: 5px 10px; font-size: 11px; }
QPushButton:disabled { color: palette(mid); }
QProgressBar {
    border: 1px solid palette(mid); border-radius: 4px; height: 7px;
    max-height: 7px;
}
QProgressBar::chunk { border-radius: 3px; }
QHeaderView::section { padding: 9px; border: 0; border-bottom: 1px solid palette(mid); }
QTableCornerButton::section { border: 0; background: palette(base); }
QTableWidget { padding: 0; border: 0; border-radius: 11px; }
QScrollBar:vertical { width: 8px; margin: 0; background: transparent; }
QScrollBar::handle:vertical { min-height: 32px; border-radius: 4px; background: palette(mid); }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""

