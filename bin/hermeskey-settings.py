#!/usr/bin/env python3
"""HermesKey settings window shell. Config editing is tracked separately in #5."""
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

SECTIONS = (
    ("Speech", "Microphone, model, and language controls will appear here."),
    ("Input", "Typing, clipboard, and focus options will appear here."),
    ("Appearance", "Overlay and audio cue options will appear here."),
    ("System", "Service status and diagnostic actions will appear here."),
)


class SettingsWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HermesKey Settings")
        self.setWindowIcon(QIcon.fromTheme("hermeskey"))
        self.setMinimumSize(680, 420)

        center = QWidget(self)
        self.setCentralWidget(center)
        layout = QVBoxLayout(center)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(16)

        title = QLabel("HermesKey Settings")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        content = QHBoxLayout()
        content.setSpacing(20)
        self.navigation = QListWidget()
        self.navigation.setAccessibleName("Settings sections")
        self.navigation.setFixedWidth(150)
        self.pages = QStackedWidget()
        for name, description in SECTIONS:
            self.navigation.addItem(name)
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(4, 4, 4, 4)
            heading = QLabel(name)
            heading.setStyleSheet("font-size: 16px; font-weight: bold;")
            page_layout.addWidget(heading)
            detail = QLabel(description)
            detail.setWordWrap(True)
            page_layout.addWidget(detail)
            page_layout.addStretch()
            self.pages.addWidget(page)
        self.navigation.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.navigation.setCurrentRow(0)
        content.addWidget(self.navigation)
        content.addWidget(self.pages, 1)
        layout.addLayout(content, 1)

        notice = QLabel("Settings editing is not available yet. Your existing config is unchanged.")
        notice.setWordWrap(True)
        layout.addWidget(notice)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Cancel
        )
        # No config wiring yet: never present a clickable save that discards edits.
        self.save_button = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        self.apply_button = self.buttons.button(QDialogButtonBox.StandardButton.Apply)
        self.save_button.setEnabled(False)
        self.apply_button.setEnabled(False)
        self.save_button.setToolTip("Available when settings editing is implemented")
        self.apply_button.setToolTip("Available when settings editing is implemented")
        self.buttons.rejected.connect(self.close)
        layout.addWidget(self.buttons)


def main() -> int:
    app = QApplication(sys.argv)
    window = SettingsWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
