from pathlib import Path
import os
import sys
import time
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import QCoreApplication

from future_epw_demo.runner import ProcessFailure, ProcessStep, WorkflowRunner


def wait_until(predicate, timeout=5.0):
    app = QCoreApplication.instance() or QCoreApplication([])
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_process_failure_contains_recent_output(tmp_path: Path):
    QCoreApplication.instance() or QCoreApplication([])
    runner = WorkflowRunner()
    failures = []
    runner.failure_reported.connect(failures.append)
    step = ProcessStep(
        "Stage 02 · CMIP6 extraction",
        [sys.executable, "-c", "print('network failed', flush=True); raise SystemExit(3)"],
        tmp_path,
        tmp_path / "stage02.log",
    )
    assert runner.run_sequence([step])
    assert wait_until(lambda: bool(failures))
    failure = failures[0]
    assert isinstance(failure, ProcessFailure)
    assert failure.exit_code == 3
    assert failure.step_name == "Stage 02 · CMIP6 extraction"
    assert "network failed" in "\n".join(failure.last_lines)
    assert failure.log_file.endswith("stage02.log")
