from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal


@dataclass(frozen=True)
class ProcessStep:
    name: str
    command: list[str]
    cwd: Path
    log_file: Path | None = None


@dataclass(frozen=True)
class ProcessFailure:
    step_name: str
    exit_code: int
    last_lines: tuple[str, ...]
    log_file: str


class WorkflowRunner(QObject):
    step_started = Signal(str)
    line_received = Signal(str, str)
    step_finished = Signal(str, int)
    sequence_finished = Signal(bool, str)
    failure_reported = Signal(object)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONUNBUFFERED", "1")
        self.process.setProcessEnvironment(env)
        self.process.readyReadStandardOutput.connect(self._read_output)
        self.process.finished.connect(self._finished)
        self._steps: list[ProcessStep] = []
        self._current: ProcessStep | None = None
        self._log_handle = None
        self._running = False
        self._recent_lines: deque[str] = deque(maxlen=30)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def current_step_name(self) -> str:
        return self._current.name if self._current else ""

    def run_sequence(self, steps: Iterable[ProcessStep]) -> bool:
        if self._running:
            return False
        self._steps = list(steps)
        if not self._steps:
            self.sequence_finished.emit(True, "")
            return True
        self._running = True
        self._start_next()
        return True

    def terminate(self) -> None:
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.terminate()

    def _start_next(self) -> None:
        if not self._steps:
            self._running = False
            self._current = None
            self.sequence_finished.emit(True, "")
            return
        self._current = self._steps.pop(0)
        self._recent_lines.clear()
        step = self._current
        if step.log_file:
            step.log_file.parent.mkdir(parents=True, exist_ok=True)
            self._log_handle = step.log_file.open("a", encoding="utf-8")
        else:
            self._log_handle = None
        self.step_started.emit(step.name)
        self.process.setWorkingDirectory(str(step.cwd))
        self.process.start(step.command[0], step.command[1:])

    def _read_output(self) -> None:
        if not self._current:
            return
        raw = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if self._log_handle:
            self._log_handle.write(raw)
            self._log_handle.flush()
        for line in raw.splitlines():
            self._recent_lines.append(line)
            self.line_received.emit(self._current.name, line)

    def _finished(self, exit_code: int, _exit_status) -> None:
        step = self._current
        name = step.name if step else ""
        log_file = str(step.log_file) if step and step.log_file else ""
        if self._log_handle:
            self._log_handle.close()
            self._log_handle = None
        self.step_finished.emit(name, int(exit_code))
        if exit_code != 0:
            failure = ProcessFailure(
                step_name=name,
                exit_code=int(exit_code),
                last_lines=tuple(self._recent_lines),
                log_file=log_file,
            )
            self.failure_reported.emit(failure)
            self._steps.clear()
            self._running = False
            self.sequence_finished.emit(False, name)
            return
        self._start_next()
