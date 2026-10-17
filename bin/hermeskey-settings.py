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

CUSTOM = "custom:"  # not a valid literal model ID or language code
MODEL_PRESETS = (
    ("Tiny — lowest resource use", "tiny"), ("Base", "base"),
    ("Small", "small"), ("Medium — default", "medium"),
    ("Large v3", "large-v3"), ("Large v3 Turbo", "large-v3-turbo"),
)
LANGUAGE_PRESETS = (
    ("Auto-detect", ""), ("English", "en"), ("Spanish", "es"),
    ("French", "fr"), ("German", "de"), ("Portuguese", "pt"),
    ("Italian", "it"), ("Japanese", "ja"), ("Korean", "ko"),
    ("Chinese", "zh"), ("Hawaiian", "haw"), ("Cantonese", "yue"),
)
SECTIONS = (
    ("Speech", "Choose the input, model and spoken language. Selecting a model does not download it."),
    ("Input", "Control typing, clipboard backup and focus safety."),
    ("Appearance", "Toggle the overlay and audio cues."),
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
                self.model_picker = QComboBox()
                self.model_picker.setObjectName("model_picker")
                for label, value in MODEL_PRESETS:
                    self.model_picker.addItem(label, value)
                self.model_picker.addItem("Custom model ID or local path…", CUSTOM)
                self.model_edit = QLineEdit()
                self.model_edit.setObjectName("model_edit")
                self.model_edit.setPlaceholderText("owner/model-id or /path/to/model")
                self.model_custom_label = QLabel("Custom model:")
                self.language_picker = QComboBox()
                self.language_picker.setObjectName("language_picker")
                for label, value in LANGUAGE_PRESETS:
                    self.language_picker.addItem(label, value)
                self.language_picker.addItem("Other language code…", CUSTOM)
                self.language_edit = QLineEdit()
                self.language_edit.setObjectName("language_edit")
                self.language_edit.setPlaceholderText("Whisper language code, e.g. nl")
                self.language_custom_label = QLabel("Other code:")
                form.addRow("Model:", self.model_picker)
                form.addRow(self.model_custom_label, self.model_edit)
                form.addRow("Language:", self.language_picker)
                form.addRow(self.language_custom_label, self.language_edit)
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
            elif name == "Input":
                form = QFormLayout()
                self.insert_picker = QComboBox()
                self.insert_picker.setObjectName("insert_picker")
                self.insert_picker.addItem("Type into the active app", "type")
                self.insert_picker.addItem("Copy to clipboard only", "clipboard")
                form.addRow("Insert mode:", self.insert_picker)
                self.clipboard_backup = QCheckBox("Keep a clipboard backup when typing")
                self.clipboard_backup.setObjectName("clipboard_backup")
                self.focus_safe = QCheckBox("Avoid inserting when focus changes")
                self.focus_safe.setObjectName("focus_safe")
                form.addRow("", self.clipboard_backup)
                form.addRow("", self.focus_safe)
                page_layout.addLayout(form)
                hint = QLabel("Clipboard mode always copies text. Focus safety needs KDE window detection; check Doctor if it cannot detect windows.")
                hint.setWordWrap(True)
                page_layout.addWidget(hint)
            elif name == "Appearance":
                self.overlay_toggle = QCheckBox("Show recording and transcribing overlay")
                self.overlay_toggle.setObjectName("overlay_toggle")
                self.sound_toggle = QCheckBox("Play start and stop cues")
                self.sound_toggle.setObjectName("sound_toggle")
                page_layout.addWidget(self.overlay_toggle)
                page_layout.addWidget(self.sound_toggle)
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
            for widget in (self.model_picker, self.model_edit, self.language_picker, self.language_edit,
                           self.source_picker, self.refresh_button, self.monitor_toggle, self.insert_picker,
                           self.clipboard_backup, self.focus_safe, self.overlay_toggle, self.sound_toggle):
                widget.setEnabled(False)
            self.notice.setText(f"Cannot load config: {self.load_error}. Edit it manually or rerun the installer.")
        else:
            self.select_existing(self.model_picker, self.model_edit, self.document.values["MODEL"])
            self.select_existing(self.language_picker, self.language_edit, self.document.values["STT_LANG"])
            self.insert_picker.setCurrentIndex(self.insert_picker.findData(self.document.values["INSERT_MODE"]))
            self.clipboard_backup.setChecked(self.document.values["COPY_TO_CLIPBOARD"] == "1")
            self.focus_safe.setChecked(self.document.values["FOCUS_SAFE_MODE"] == "1")
            self.overlay_toggle.setChecked(self.document.values["OVERLAY_ENABLED"] == "1")
            self.sound_toggle.setChecked(self.document.values["SOUND_ENABLED"] == "1")
            self.populate_sources()
            self.refresh_sources()
            self.notice.setText(f"Editing {self.path}. Other settings and comments are preserved.")
            if path is None and (
                os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")) != str(Path.home() / ".config")
                or os.environ.get("HERMESKEY_CONFIG")
            ):
                self.notice.setText(self.notice.text() + " Custom config overrides are not used by the systemd service.")
        self.model_picker.currentIndexChanged.connect(self.update_model_control)
        self.language_picker.currentIndexChanged.connect(self.update_language_control)
        self.insert_picker.currentIndexChanged.connect(self.update_insert_mode)
        self.model_edit.textChanged.connect(self.update_buttons)
        self.language_edit.textChanged.connect(self.update_buttons)
        self.source_picker.currentIndexChanged.connect(self.update_buttons)
        for toggle in (self.clipboard_backup, self.focus_safe, self.overlay_toggle, self.sound_toggle):
            toggle.toggled.connect(self.update_buttons)
        self.update_model_control()
        self.update_language_control()
        self.update_insert_mode()
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

    @staticmethod
    def select_existing(picker: QComboBox, editor: QLineEdit, value: str) -> None:
        index = picker.findData(value)
        if index < 0:
            index = picker.findData(CUSTOM)
        picker.setCurrentIndex(index)
        editor.setText(value)

    def update_model_control(self) -> None:
        custom = self.model_picker.currentData() == CUSTOM
        self.model_edit.setHidden(not custom)
        self.model_custom_label.setHidden(not custom)
        self.update_buttons()

    def update_language_control(self) -> None:
        custom = self.language_picker.currentData() == CUSTOM
        self.language_edit.setHidden(not custom)
        self.language_custom_label.setHidden(not custom)
        self.update_buttons()

    def update_insert_mode(self) -> None:
        self.clipboard_backup.setEnabled(self.document is not None and self.insert_picker.currentData() == "type")
        self.update_buttons()

    def changes(self) -> dict[str, str]:
        if self.document is None:
            return {}
        proposed = {
            "MODEL": self.model_edit.text() if self.model_picker.currentData() == CUSTOM else self.model_picker.currentData(),
            "STT_LANG": self.language_edit.text() if self.language_picker.currentData() == CUSTOM else self.language_picker.currentData(),
            "RECORD_SOURCE": self.source_picker.currentData(),
            "INSERT_MODE": self.insert_picker.currentData(),
            "COPY_TO_CLIPBOARD": "1" if self.clipboard_backup.isChecked() else "0",
            "FOCUS_SAFE_MODE": "1" if self.focus_safe.isChecked() else "0",
            "OVERLAY_ENABLED": "1" if self.overlay_toggle.isChecked() else "0",
            "SOUND_ENABLED": "1" if self.sound_toggle.isChecked() else "0",
        }
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
            for key, value in values.items():
                stream.write(f"{key}={value}\n")
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
        # Hotkey behavior and microphone choice are read per invocation.
        if not ({"MODEL", "STT_LANG"} & changes.keys()):
            self.notice.setText(self.notice.text() + " Changes take effect on the next hotkey invocation.")
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
