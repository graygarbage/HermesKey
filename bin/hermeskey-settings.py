#!/usr/bin/env python3
"""Small native settings editor; only MODEL and STT_LANG are editable so far."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from hermeskey_settings_config import ConfigDocument, ConfigError, canonical_path

SECTIONS = (
    ("Speech", "Model and language; microphone source selection is coming later."),
    ("Input", "Typing, clipboard, and focus options will appear here."),
    ("Appearance", "Overlay and audio cue options will appear here."),
    ("System", "Service status and diagnostic actions will appear here."),
)


class SettingsWindow(QMainWindow):
    def __init__(self, path: Path | None = None):
        super().__init__()
        self.setWindowTitle("HermesKey Settings")
        self.setWindowIcon(QIcon.fromTheme("hermeskey"))
        self.setMinimumSize(680, 420)
        self.path = path or canonical_path()
        self._discarding = False
        try:
            self.document = ConfigDocument(self.path)
            self.load_error = None
        except ConfigError as exc:
            self.document = None
            self.load_error = str(exc)

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
            if name == "Speech":
                form = QFormLayout()
                self.model_edit = QLineEdit()
                self.model_edit.setObjectName("model_edit")
                self.model_edit.setPlaceholderText("medium or owner/model-id")
                self.language_edit = QLineEdit()
                self.language_edit.setObjectName("language_edit")
                self.language_edit.setPlaceholderText("en (empty = auto-detect)")
                form.addRow("Model:", self.model_edit)
                form.addRow("Language:", self.language_edit)
                page_layout.addLayout(form)
            page_layout.addStretch()
            self.pages.addWidget(page)
        self.navigation.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.navigation.setCurrentRow(0)
        content.addWidget(self.navigation)
        content.addWidget(self.pages, 1)
        layout.addLayout(content, 1)

        self.notice = QLabel()
        self.notice.setWordWrap(True)
        layout.addWidget(self.notice)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.save_button = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        self.apply_button = self.buttons.button(QDialogButtonBox.StandardButton.Apply)
        self.save_button.clicked.connect(lambda: self.save_changes(close=True))
        self.apply_button.clicked.connect(self.save_changes)
        self.buttons.rejected.connect(self.discard_and_close)
        layout.addWidget(self.buttons)

        if self.document is None:
            self.model_edit.setEnabled(False)
            self.language_edit.setEnabled(False)
            self.notice.setText(f"Cannot load config: {self.load_error}. Edit it manually or rerun the installer.")
        else:
            self.model_edit.setText(self.document.values["MODEL"])
            self.language_edit.setText(self.document.values["STT_LANG"])
            self.notice.setText(f"Editing {self.path}. Other settings and comments are preserved.")
            if path is None and (
                os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")) != str(Path.home() / ".config")
                or os.environ.get("HERMESKEY_CONFIG")
            ):
                self.notice.setText(self.notice.text() + " Custom config overrides are not used by the systemd service.")
        self.model_edit.textChanged.connect(self.update_buttons)
        self.language_edit.textChanged.connect(self.update_buttons)
        self.update_buttons()

    def changes(self) -> dict[str, str]:
        if self.document is None:
            return {}
        proposed = {"MODEL": self.model_edit.text(), "STT_LANG": self.language_edit.text()}
        return {key: value for key, value in proposed.items() if self.document.values[key] != value}

    def update_buttons(self) -> None:
        enabled = bool(self.changes())
        self.save_button.setEnabled(enabled)
        self.apply_button.setEnabled(enabled)

    @staticmethod
    def validate(path: Path) -> None:
        # Doctor sources its input as shell. Pass it ONLY two already-validated
        # literals, never the full config with unknown user expressions.
        values = ConfigDocument(path).values
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix=".hermeskey-check-",
                                         dir=path.parent, delete=False) as stream:
            check_path = Path(stream.name)
            stream.write(f'MODEL={values["MODEL"]}\nSTT_LANG={values["STT_LANG"]}\n')
        try:
            env = dict(os.environ, HERMESKEY_CONFIG=str(check_path))
            doctor = Path(__file__).with_name("hermeskey-doctor")
            try:
                result = subprocess.run(
                    ["bash", str(doctor), "--config-only"], env=env,
                    capture_output=True, text=True, timeout=20, check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise ConfigError("Could not run Doctor to validate proposed settings") from exc
            if result.returncode != 0:
                details = [line for line in result.stdout.splitlines() if line.startswith("❌")]
                raise ConfigError("Doctor rejected the proposed config: " + "; ".join(details[:4]))
        finally:
            check_path.unlink(missing_ok=True)

    def save_changes(self, close: bool = False) -> bool:
        if self.document is None or not self.changes():
            return False
        try:
            self.document.save(self.changes(), self.validate)
        except (ConfigError, OSError) as exc:
            QMessageBox.warning(self, "Settings not saved", str(exc))
            return False
        self.update_buttons()
        self.notice.setText(f"Saved {self.path}. Other settings and comments were preserved.")
        answer = QMessageBox.question(
            self, "Restart speech service?",
            "Model or language changes require restarting hermeskey.service. "
            "This can interrupt active dictation. Restart now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            try:
                subprocess.run(["systemctl", "--user", "restart", "hermeskey.service"],
                               timeout=15, check=True, capture_output=True)
            except (OSError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
                QMessageBox.warning(self, "Restart failed", "Settings were saved. Restart hermeskey.service manually.")
        else:
            self.notice.setText(self.notice.text() + " Restart hermeskey.service to apply the changes.")
        if close:
            self.close()
        return True

    def discard_and_close(self) -> None:
        self._discarding = True
        self.close()

    def closeEvent(self, event) -> None:
        if self.changes() and not self._discarding:
            answer = QMessageBox.question(
                self, "Discard changes?", "Close without saving your settings?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        event.accept()


def main() -> int:
    app = QApplication(sys.argv)
    window = SettingsWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
