"""Asynchronous, local-only service status and support actions in Settings."""
import json
import sys
from pathlib import Path

from PySide6.QtCore import QProcess, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QMessageBox,
    QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)

from hermeskey_system_tools import UNITS


class SystemPanel(QWidget):
    restartRequested = Signal(object)
    openConfigRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.processes = {}
        self.statuses = {}
        layout = QVBoxLayout(self)
        self.labels = {}
        for unit, title in ((UNITS[0], "Speech server"), (UNITS[1], "Typing daemon")):
            label = QLabel(f"{title}: Checking…")
            label.setObjectName(unit)
            self.labels[unit] = label
            layout.addWidget(label)
        row = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh status")
        self.speech_button = QPushButton("Restart speech server")
        self.typing_button = QPushButton("Restart typing daemon")
        self.both_button = QPushButton("Restart both")
        row.addWidget(self.refresh_button)
        row.addWidget(self.speech_button)
        row.addWidget(self.typing_button)
        row.addWidget(self.both_button)
        layout.addLayout(row)
        row = QHBoxLayout()
        self.logs_button = QPushButton("Open logs")
        self.doctor_button = QPushButton("Run Doctor")
        self.config_button = QPushButton("Open advanced config file")
        row.addWidget(self.logs_button)
        row.addWidget(self.doctor_button)
        row.addWidget(self.config_button)
        row.addStretch()
        layout.addLayout(row)
        hint = QLabel("Restarts can interrupt recording, transcription or typing. Logs and diagnostics stay on this machine; review before sharing.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addStretch()
        self.refresh_button.clicked.connect(self.refresh)
        self.speech_button.clicked.connect(lambda: self.restartRequested.emit((UNITS[0],)))
        self.typing_button.clicked.connect(lambda: self.restartRequested.emit((UNITS[1],)))
        self.both_button.clicked.connect(lambda: self.restartRequested.emit(UNITS))
        self.logs_button.clicked.connect(lambda: self.show_report("Logs", [sys.executable, str(Path(__file__).with_name("hermeskey_system_tools.py")), "logs"]))
        self.doctor_button.clicked.connect(lambda: self.show_report("Doctor", ["bash", str(Path(__file__).with_name("hermeskey-doctor"))]))
        self.config_button.clicked.connect(self.openConfigRequested.emit)
        self.poll = QTimer(self)
        self.poll.setInterval(8000)
        self.poll.timeout.connect(self.refresh)

    def activate(self):
        self.poll.start()
        self.refresh()

    def deactivate(self):
        self.poll.stop()

    def run_process(self, slot, program, args, finished, timeout=10000):
        if slot in self.processes:
            return False
        process = QProcess(self)
        self.processes[slot] = process
        buffer = bytearray()
        timer = QTimer(process)
        timer.setSingleShot(True)

        def collect():
            buffer.extend(bytes(process.readAllStandardOutput()))
            if len(buffer) > 65536:
                process.setProperty("too_large", True)
                process.kill()

        def done(code, status):
            if self.processes.get(slot) is not process:
                return
            timer.stop()
            collect()
            self.processes.pop(slot, None)
            process.deleteLater()
            ok = (status == QProcess.ExitStatus.NormalExit and code == 0 and
                  not process.property("timed_out") and not process.property("too_large"))
            finished(ok, bytes(buffer[:65536]).decode("utf-8", errors="replace"))

        process.readyReadStandardOutput.connect(collect)
        process.finished.connect(done)
        process.errorOccurred.connect(lambda error: done(1, QProcess.ExitStatus.CrashExit)
                                      if error == QProcess.ProcessError.FailedToStart else None)
        timer.timeout.connect(lambda: (process.setProperty("timed_out", True), process.kill()))
        timer.start(timeout)
        process.start(program, args)
        return True

    def refresh(self):
        if "status" in self.processes:
            return
        helper = Path(__file__).with_name("hermeskey_system_tools.py")

        def show(ok, output):
            try:
                states = json.loads(output) if ok else {}
            except ValueError:
                states = {}
            self.statuses = states
            for unit, label in self.labels.items():
                info = states.get(unit, {})
                active = info.get("active", "unknown")
                ready = info.get("ready")
                if active == "active":
                    if ready is True:
                        status = "Ready"
                    elif ready is None:
                        status = "Running; readiness unknown (custom socket)"
                    else:
                        status = "Running; speech server not responding (loading or busy)" if unit == UNITS[0] else "Running; typing socket unavailable"
                else:
                    status = active.capitalize()
                    if active == "failed" and info.get("result"):
                        status += f" ({info['result']})"
                label.setText(("Speech server" if unit == UNITS[0] else "Typing daemon") + f": {status}")

        self.run_process("status", sys.executable, [str(helper), "status"], show, timeout=7000)

    def restart_units(self, units):
        if "action" in self.processes or not units or any(unit not in UNITS for unit in units):
            return
        self.set_actions_enabled(False)
        for unit in units:
            self.labels[unit].setText(("Speech server" if unit == UNITS[0] else "Typing daemon") + ": Restart requested…")

        def done(ok, _output):
            self.set_actions_enabled(True)
            if not ok:
                QMessageBox.warning(self, "Restart failed", "systemctl --user could not restart the selected service(s). Check the local service journal.")
            # systemctl returning 0 is NOT proof of model or typing readiness.
            self.refresh()

        if not self.run_process("action", "systemctl", ["--user", "restart", *units], done, timeout=20000):
            self.set_actions_enabled(True)

    def set_actions_enabled(self, enabled):
        for button in (self.speech_button, self.typing_button, self.both_button, self.doctor_button, self.logs_button, self.config_button):
            button.setEnabled(enabled)

    def show_report(self, title, command):
        if "action" in self.processes:
            return
        self.set_actions_enabled(False)

        def done(ok, output):
            self.set_actions_enabled(True)
            if not output and not ok:
                output = "Command unavailable or timed out. Check that the user service and system tools are installed."
            if not ok:
                output = "Diagnostic command did not complete successfully.\n\n" + output
            dialog = QDialog(self)
            dialog.setWindowTitle(f"HermesKey {title} (local only)")
            dialog.resize(820, 560)
            box = QVBoxLayout(dialog)
            viewer = QPlainTextEdit()
            viewer.setReadOnly(True)
            viewer.setPlainText(output)
            box.addWidget(viewer)
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            buttons.rejected.connect(dialog.reject)
            box.addWidget(buttons)
            dialog.exec()
            viewer.clear()
            dialog.deleteLater()

        self.run_process("action", command[0], command[1:], done, timeout=30000)

    def stop(self):
        self.poll.stop()
        pending = list(self.processes.values())
        self.processes.clear()  # callbacks must not display dialogs during close
        for process in pending:
            if process.state() != QProcess.ProcessState.NotRunning:
                process.kill()
                process.waitForFinished(1000)
