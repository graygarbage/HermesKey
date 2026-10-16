#!/usr/bin/env python3
"""Small native settings editor for speech model, language and input source."""
import os
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

from PySide6.QtCore import Qt, QProcess, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from hermeskey_audio_sources import SourceDiscoveryError, parse_json_sources, parse_short_sources
from hermeskey_settings_config import ConfigDocument, ConfigError, canonical_path

SECTIONS = (
    ("Speech", "Choose the input for the next recording, plus model and language."),
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
        self.sources = []
        self.source_process = None
        self._source_initialized = False
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
                self.source_picker = QComboBox()
                self.source_picker.setObjectName("source_picker")
                self.source_picker.addItem("System default microphone (follows desktop setting)", "default")
                self.refresh_button = QPushButton("Refresh sources")
                self.monitor_toggle = QCheckBox("Show monitor sources (system audio)")
                self.source_status = QLabel()
                self.source_status.setWordWrap(True)
                form.addRow("Microphone:", self.source_picker)
                form.addRow("", self.refresh_button)
                form.addRow("", self.monitor_toggle)
                page_layout.addLayout(form)
                page_layout.addWidget(self.source_status)
                self.refresh_button.clicked.connect(self.refresh_sources)
                self.monitor_toggle.toggled.connect(self.populate_sources)
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
            self.source_picker.setEnabled(False)
            self.refresh_button.setEnabled(False)
            self.monitor_toggle.setEnabled(False)
            self.notice.setText(f"Cannot load config: {self.load_error}. Edit it manually or rerun the installer.")
        else:
            self.model_edit.setText(self.document.values["MODEL"])
            self.language_edit.setText(self.document.values["STT_LANG"])
            self.populate_sources()
            self.refresh_sources()
            self.notice.setText(f"Editing {self.path}. Other settings and comments are preserved.")
            if path is None and (
                os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")) != str(Path.home() / ".config")
                or os.environ.get("HERMESKEY_CONFIG")
            ):
                self.notice.setText(self.notice.text() + " Custom config overrides are not used by the systemd service.")
        self.model_edit.textChanged.connect(self.update_buttons)
        self.language_edit.textChanged.connect(self.update_buttons)
        self.source_picker.currentIndexChanged.connect(self.update_buttons)
        self.update_buttons()

    def refresh_sources(self) -> None:
        if self.source_process is not None or self.document is None:
            return
        self.refresh_button.setEnabled(False)
        self.source_status.setText("Looking for microphone sources…")
        self._start_source_process(json_format=True)

    def _start_source_process(self, json_format: bool) -> None:
        process = QProcess(self)
        self.source_process = process
        timer = QTimer(process)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: (process.setProperty("timed_out", True), process.kill()))
        process.finished.connect(
            lambda code, status: self._source_finished(process, timer, json_format, code, status)
        )
        process.errorOccurred.connect(
            lambda error: self._source_failed_to_start(process, timer, json_format, error)
        )
        args = ["-f", "json", "list", "sources"] if json_format else ["list", "short", "sources"]
        timer.start(5000)
        process.start("pactl", args)

    def _source_failed_to_start(self, process, timer, json_format, error) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            self._complete_source_attempt(process, timer, json_format, None)

    def _source_finished(self, process, timer, json_format, code, status) -> None:
        output = None
        if status == QProcess.ExitStatus.NormalExit and code == 0 and not process.property("timed_out"):
            output = bytes(process.readAllStandardOutput()).decode("utf-8", errors="replace")
        self._complete_source_attempt(process, timer, json_format, output)

    def _complete_source_attempt(self, process, timer, json_format, output) -> None:
        if process is not self.source_process:
            return
        timer.stop()
        self.source_process = None
        process.deleteLater()
        try:
            if output is None:
                raise SourceDiscoveryError("pactl unavailable")
            sources = parse_json_sources(output) if json_format else parse_short_sources(output)
        except SourceDiscoveryError:
            if json_format:
                self._start_source_process(json_format=False)
                return
            self.source_status.setText("Cannot refresh sources; check PipeWire/PulseAudio. Your selection is unchanged.")
        else:
            self.sources = sources
            self.populate_sources()
            count = sum(not source.is_monitor for source in sources)
            self.source_status.setText(
                f"{count} microphone source(s) found. Choosing a source changes HermesKey only, not the desktop default."
                if count else "No microphones found. You can keep System default or refresh after connecting a device."
            )
        self.refresh_button.setEnabled(True)

    def populate_sources(self) -> None:
        if self.document is None:
            return
        chosen = (self.source_picker.currentData() if self._source_initialized else self.document.values["RECORD_SOURCE"])
        chosen = chosen or self.document.values["RECORD_SOURCE"]
        self.source_picker.blockSignals(True)
        self.source_picker.clear()
        self.source_picker.addItem("System default microphone (follows desktop setting)", "default")
        names = {"default"}
        visible = [source for source in self.sources
                   if not source.is_monitor or self.monitor_toggle.isChecked() or source.name == chosen]
        descriptions = Counter(source.description for source in visible)
        for source in visible:
            if source.name in names:
                continue
            names.add(source.name)
            label = source.description
            if descriptions[source.description] > 1:
                label += f" — {source.name}"
            if source.is_monitor:
                label += " (system audio monitor)"
            self.source_picker.addItem(label, source.name)
            self.source_picker.setItemData(self.source_picker.count() - 1, source.name, Qt.ItemDataRole.ToolTipRole)
        if chosen not in names:
            self.source_picker.addItem(f"Unavailable: {chosen}", chosen)
            self.source_picker.setItemData(self.source_picker.count() - 1, chosen, Qt.ItemDataRole.ToolTipRole)
        index = self.source_picker.findData(chosen)
        self.source_picker.setCurrentIndex(index if index >= 0 else 0)
        self.source_picker.blockSignals(False)
        self._source_initialized = True
        self.update_buttons()

    def changes(self) -> dict[str, str]:
        if self.document is None:
            return {}
        proposed = {"MODEL": self.model_edit.text(), "STT_LANG": self.language_edit.text(),
                    "RECORD_SOURCE": self.source_picker.currentData()}
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
            stream.write(f'MODEL={values["MODEL"]}\nSTT_LANG={values["STT_LANG"]}\n'
                         f'RECORD_SOURCE={values["RECORD_SOURCE"]}\n')
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
        changes = self.changes()
        try:
            self.document.save(changes, self.validate)
        except (ConfigError, OSError) as exc:
            QMessageBox.warning(self, "Settings not saved", str(exc))
            return False
        self.update_buttons()
        self.notice.setText(f"Saved {self.path}. Other settings and comments were preserved.")
        # Microphone choice is read on each hotkey invocation, not by the
        # long-lived speech server. Never restart it for a mic-only change.
        if not ({"MODEL", "STT_LANG"} & changes.keys()):
            self.notice.setText(self.notice.text() + " The new microphone is used for the next recording.")
            if close:
                self.close()
            return True
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
        process = self.source_process
        self.source_process = None  # callbacks must not start fallback while closing
        if process is not None and process.state() != QProcess.ProcessState.NotRunning:
            process.kill()
            process.waitForFinished(1000)
        event.accept()


def main() -> int:
    app = QApplication(sys.argv)
    window = SettingsWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
