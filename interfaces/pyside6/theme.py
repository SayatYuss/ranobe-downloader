"""Compact neutral Qt styling with system/light/dark palette support."""
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

def apply_theme(app: QApplication, mode: str = "system"):
    app.setStyle("Fusion")
    if mode == "system":
        app.setPalette(app.style().standardPalette())
        app.setStyleSheet(STYLE)
        return
    dark = mode == "dark"
    base = "#202124" if dark else "#ffffff"
    surface = "#292b2e" if dark else "#f6f6f6"
    text = "#eeeeee" if dark else "#202124"
    muted = "#b9bcc1" if dark else "#666a70"
    outline = "#45484c" if dark else "#d7dade"
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(base))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(text))
    palette.setColor(QPalette.ColorRole.Base, QColor(surface))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(base))
    palette.setColor(QPalette.ColorRole.Text, QColor(text))
    palette.setColor(QPalette.ColorRole.Button, QColor(surface))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(text))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#747b83" if dark else "#a5abb2"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff" if dark else "#141414"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(muted))
    app.setPalette(palette)
    app.setStyleSheet(STYLE + f"""
        QWidget {{ color: {text}; }}
        QLineEdit, QComboBox, QTableWidget, QPlainTextEdit {{ background: {surface}; border-color: {outline}; }}
        QPushButton {{ background: {surface}; border-color: {outline}; }}
        QPushButton:hover {{ background: {'#34373a' if dark else '#e9eaec'}; }}
    """)

STYLE = """
QWidget { font-size: 13px; }
QMainWindow { background: palette(window); }
QTabWidget::pane { border: 0; }
QTabBar::tab { padding: 11px 20px; margin-right: 3px; border-bottom: 2px solid transparent; }
QTabBar::tab:selected { border-bottom: 2px solid palette(window-text); font-weight: 600; }
QLineEdit, QComboBox, QPlainTextEdit, QTableWidget {
    border: 1px solid palette(mid); border-radius: 6px; padding: 7px;
}
QPushButton { padding: 8px 16px; border: 1px solid palette(mid); border-radius: 6px; }
QPushButton:disabled { opacity: 0.5; }
QProgressBar { border: 1px solid palette(mid); border-radius: 4px; text-align: center; height: 12px; }
QProgressBar::chunk { background: palette(midlight); border-radius: 3px; }
QHeaderView::section { padding: 8px; border: 0; border-bottom: 1px solid palette(mid); }
"""
