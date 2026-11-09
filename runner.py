"""
runner.py — command execution with live, streamed output.

Uses QProcess so output lands on the Qt event loop without blocking the
touch UI. A single CommandRunner owns at most one active process; starting
a new one while something runs is refused (the UI greys the grid instead).

Nothing here implements an attack. It shells out to whatever binary a
tools.yaml entry names — the same binaries you'd run by hand on an
authorized engagement. Keep that file scoped to targets you're allowed
to touch.
"""

from __future__ import annotations

import os
import shlex

from PySide6.QtCore import QObject, QProcess, Signal


class CommandRunner(QObject):
    output = Signal(str)          # chunk of combined stdout/stderr
    started = Signal(str)         # the resolved command line
    finished = Signal(int)        # exit code (-1 if killed/crashed)
    state_changed = Signal(bool)  # True = running

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._proc: QProcess | None = None

    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.state() != QProcess.NotRunning

    def start(self, command: str, cwd: str | None = None, shell: bool = False) -> bool:
        if self.running:
            self.output.emit("\n[!] A command is already running. Stop it first.\n")
            return False

        self._proc = QProcess(self)
        self._proc.setProcessChannelMode(QProcess.MergedChannels)
        if cwd and os.path.isdir(cwd):
            self._proc.setWorkingDirectory(cwd)

        self._proc.readyReadStandardOutput.connect(self._on_read)
        self._proc.finished.connect(self._on_finished)
        self._proc.errorOccurred.connect(self._on_error)

        if shell:
            # Let the shell handle pipes/redirects when an entry needs them.
            self._proc.start("/bin/bash", ["-lc", command])
        else:
            parts = shlex.split(command)
            if not parts:
                self.output.emit("[!] Empty command.\n")
                return False
            self._proc.start(parts[0], parts[1:])

        self.started.emit(command)
        self.state_changed.emit(True)
        return True

    def stop(self) -> None:
        if not self.running or self._proc is None:
            return
        self.output.emit("\n[*] Sending SIGTERM...\n")
        self._proc.terminate()
        if not self._proc.waitForFinished(3000):
            self.output.emit("[*] Not responding, sending SIGKILL...\n")
            self._proc.kill()
            self._proc.waitForFinished(1500)

    # ---- QProcess callbacks ----------------------------------------------

    def _on_read(self) -> None:
        if self._proc is None:
            return
        data = bytes(self._proc.readAllStandardOutput()).decode("utf-8", "replace")
        if data:
            self.output.emit(data)

    def _on_finished(self, code: int, _status) -> None:
        self.output.emit(f"\n[=] Exited with code {code}.\n")
        self.finished.emit(code)
        self.state_changed.emit(False)
        self._proc = None

    def _on_error(self, err) -> None:
        mapping = {
            QProcess.FailedToStart: "failed to start (binary not installed / not on PATH?)",
            QProcess.Crashed: "crashed",
            QProcess.Timedout: "timed out",
            QProcess.WriteError: "write error",
            QProcess.ReadError: "read error",
        }
        self.output.emit(f"\n[!] Process error: {mapping.get(err, 'unknown')}.\n")
        self.state_changed.emit(False)
