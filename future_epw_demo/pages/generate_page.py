from __future__ import annotations

import csv
import re
from dataclasses import replace
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..backend import WorkflowBackend
from ..demo_state import WorkflowState, expected_epw_count
from ..i18n import Translator, bind_text, retranslate_tree
from ..project_workspace import ProjectWorkspace
from ..preflight import run_generation_preflight
from ..runner import ProcessFailure, ProcessStep, WorkflowRunner
from ..workflow_state import WorkflowStateStore
from ..widgets import data_panel, page_header, pipeline_node, research_strip, status_pill

_GENERATE_RE = re.compile(r"\[(\d+)/(\d+)\]\s+generate\s+(.+?)\s+(ssp\d+)\s+(\d{4})\s+(.+)$", re.I)


class GeneratePage(QWidget):
    def __init__(
        self,
        state: WorkflowState,
        backend: WorkflowBackend,
        runner: WorkflowRunner,
        workspace_provider: Callable[[], ProjectWorkspace | None],
        on_state_change: Callable[[], None] | None = None,
        translator: Translator | None = None,
    ):
        super().__init__()
        self.state = state
        self.backend = backend
        self.runner = runner
        self.workspace_provider = workspace_provider
        self.on_state_change = on_state_change or (lambda: None)
        self.tr = translator or Translator()

        self.runner.step_started.connect(self._step_started)
        self.runner.line_received.connect(self._line_received)
        self.runner.step_finished.connect(self._step_finished)
        self.runner.sequence_finished.connect(self._sequence_finished)
        self.runner.failure_reported.connect(self._failure_reported)
        self._last_failure: ProcessFailure | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 24)
        root.setSpacing(13)
        title, subtitle = page_header(
            "Generate EPW",
            "Translate validated monthly climate signals into auditable future EPW weather files",
            translator=self.tr, title_key="generate.title", subtitle_key="generate.subtitle",
        )
        root.addWidget(title)
        root.addWidget(subtitle)

        self.summary_strip = research_strip([
            ("Stage 03", "Offline", "Climate-factor synthesis"),
            ("Stage 04", "Offline", "Future EPW morphing"),
            ("Stage 05", "QA", "Automatic validation after generation"),
            ("Outputs", f"{expected_epw_count(state)} EPW", "Per-GCM + ensemble mean"),
        ])
        strip_keys = [
            ("generate.strip.stage03", "generate.strip.stage03.value", "generate.strip.stage03.detail"),
            ("generate.strip.stage04", "generate.strip.stage04.value", "generate.strip.stage04.detail"),
            ("generate.strip.stage05", "generate.strip.stage05.value", "generate.strip.stage05.detail"),
            ("generate.strip.outputs", None, "generate.strip.outputs.detail"),
        ]
        for idx, (kicker_key, value_key, detail_key) in enumerate(strip_keys):
            cell = self.summary_strip.layout().itemAt(idx).widget()
            labels = cell.findChildren(QLabel)
            if len(labels) >= 3:
                bind_text(labels[0], kicker_key, self.tr)
                if value_key:
                    bind_text(labels[1], value_key, self.tr)
                bind_text(labels[2], detail_key, self.tr)
        root.addWidget(self.summary_strip)

        pipeline, pipeline_layout = data_panel(
            "Production pipeline",
            "The validated Stage 03 → Stage 04 → Stage 05 chain runs locally after CMIP6 cache completion.",
            translator=self.tr, title_key="generate.pipeline.title", subtitle_key="generate.pipeline.subtitle",
        )
        self.stage03_node = pipeline_node(
            "Stage 03", "Climate Factors",
            "Build historical/future climatologies and variable-specific monthly change factors.",
            "WAITING", "pending",
        )
        self.stage04_node = pipeline_node(
            "Stage 04", "Future EPW morphing",
            "Apply monthly CMIP6 signals to the baseline hourly weather skeleton and write EPW outputs.",
            "WAITING", "pending",
        )
        self.stage05_node = pipeline_node(
            "Stage 05", "Validation",
            "Validate 8760-hour EPWs, physical bounds and target-vs-achieved audit groups.",
            "WAITING", "pending",
        )
        pipeline_keys = [
            (self.stage03_node, "generate.pipeline.stage03.title", "generate.pipeline.stage03.detail"),
            (self.stage04_node, "generate.pipeline.stage04.title", "generate.pipeline.stage04.detail"),
            (self.stage05_node, "generate.pipeline.stage05.title", "generate.pipeline.stage05.detail"),
        ]
        for node, title_key, detail_key in pipeline_keys:
            for label in node.findChildren(QLabel):
                if label.objectName() == "PipelineTitle":
                    bind_text(label, title_key, self.tr)
                elif label.objectName() == "PipelineDetail":
                    bind_text(label, detail_key, self.tr)
                elif label.objectName() == "StatusPill":
                    bind_text(label, "generate.pipeline.waiting", self.tr)
            pipeline_layout.addWidget(node)
        root.addWidget(pipeline)

        middle = QHBoxLayout()
        middle.setSpacing(13)

        factors, factors_layout = data_panel(
            "Climate signal summary",
            "Stage 03 metadata is loaded directly from the active project workspace.",
            translator=self.tr, title_key="generate.factor.title", subtitle_key="generate.factor.subtitle",
        )
        factor_grid = QGridLayout()
        self.climatology_value = QLabel("—")
        self.per_gcm_value = QLabel("—")
        self.ensemble_value = QLabel("—")
        self.fallback_value = QLabel("—")
        factor_items = [
            ("CLIMATOLOGY ROWS", "generate.factor.climatology", self.climatology_value),
            ("PER-GCM FACTORS", "generate.factor.per_gcm", self.per_gcm_value),
            ("ENSEMBLE ROWS", "generate.factor.ensemble", self.ensemble_value),
            ("PRECIP. FALLBACK", "generate.factor.fallback", self.fallback_value),
        ]
        for i, (name, text_key, value) in enumerate(factor_items):
            row, col = divmod(i, 2)
            key = QLabel(name)
            bind_text(key, text_key, self.tr)
            key.setObjectName("TinyLabel")
            value.setObjectName("QaValue")
            factor_grid.addWidget(key, row * 2, col)
            factor_grid.addWidget(value, row * 2 + 1, col)
        factors_layout.addLayout(factor_grid)
        self.warning_summary = QLabel(self.tr.text("generate.factor.none"))
        self.warning_summary.setObjectName("Muted")
        factors_layout.addWidget(self.warning_summary)
        factor_actions = QHBoxLayout()
        factor_btn = QPushButton("View Climate Factors")
        bind_text(factor_btn, "generate.factor.view", self.tr)
        factor_btn.clicked.connect(self._show_factors)
        warn_btn = QPushButton("View Warnings")
        bind_text(warn_btn, "generate.factor.warnings", self.tr)
        warn_btn.clicked.connect(self._show_warning)
        factor_actions.addWidget(factor_btn)
        factor_actions.addWidget(warn_btn)
        factor_actions.addStretch()
        factors_layout.addLayout(factor_actions)
        middle.addWidget(factors, 3)

        preflight, preflight_layout = data_panel(
            "Preflight integrity",
            "Generation is enabled only after all CMIP6 assets required by the active climate selection are available.",
            translator=self.tr, title_key="generate.preflight.title", subtitle_key="generate.preflight.subtitle",
        )
        self.preflight_labels: dict[str, QLabel] = {}
        preflight_key_map = {
            "Project": "generate.preflight.project", "Baseline EPW": "generate.preflight.baseline",
            "Location": "generate.preflight.location", "Protocol R1": "generate.preflight.protocol",
            "Climate selection": "generate.preflight.selection",
            "Manifest": "generate.preflight.manifest", "CMIP6 cache": "generate.preflight.cache",
            "Output directory": "generate.preflight.output", "Workflow idle": "generate.preflight.idle",
        }
        for name in [
            "Project", "Baseline EPW", "Location", "Protocol R1", "Climate selection",
            "Manifest", "CMIP6 cache", "Output directory", "Workflow idle",
        ]:
            row = QHBoxLayout()
            pill = status_pill("WAIT", "pending")
            self.preflight_labels[name] = pill
            row.addWidget(pill)
            text_label = QLabel(name)
            bind_text(text_label, preflight_key_map[name], self.tr)
            row.addWidget(text_label)
            row.addStretch()
            preflight_layout.addLayout(row)
        middle.addWidget(preflight, 2)
        root.addLayout(middle)

        generation, generation_layout = data_panel(
            "EPW generation queue",
            "Stage 04 writes each model/scenario/time-slice case independently using deterministic filenames.",
            translator=self.tr, title_key="generate.queue.title", subtitle_key="generate.queue.subtitle",
        )
        queue_top = QHBoxLayout()
        self.expected_label = QLabel()
        self.expected_label.setObjectName("QaValue")
        self.generated_label = QLabel()
        self.generated_label.setObjectName("QaValue")
        self.current_case = QLabel(self.tr.text("generate.queue.ready"))
        self.current_case.setObjectName("MonoValue")
        for title_text, text_key, value_widget in [
            ("EXPECTED OUTPUTS", "generate.queue.expected", self.expected_label),
            ("GENERATED", "generate.queue.generated", self.generated_label),
            ("CURRENT CASE", "generate.queue.current", self.current_case),
        ]:
            col = QVBoxLayout()
            lab = QLabel(title_text)
            bind_text(lab, text_key, self.tr)
            lab.setObjectName("TinyLabel")
            col.addWidget(lab)
            col.addWidget(value_widget)
            queue_top.addLayout(col, 1)
        generation_layout.addLayout(queue_top)
        self.progress = QProgressBar()
        generation_layout.addWidget(self.progress)
        controls = QHBoxLayout()
        self.generate_btn = QPushButton("Build Factors + Generate + Validate")
        bind_text(self.generate_btn, "generate.button.run", self.tr)
        self.generate_btn.setObjectName("PrimaryButton")
        self.generate_btn.clicked.connect(self.start_generation)
        self.stop_btn = QPushButton("Stop")
        bind_text(self.stop_btn, "generate.button.stop", self.tr)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setToolTip(self.tr.text("generate.stop.tooltip"))
        open_btn = QPushButton("Open folder")
        bind_text(open_btn, "generate.button.open", self.tr)
        open_btn.clicked.connect(self._open_folder)
        controls.addWidget(self.generate_btn)
        controls.addWidget(self.stop_btn)
        controls.addStretch()
        controls.addWidget(open_btn)
        generation_layout.addLayout(controls)
        root.addWidget(generation)

        self.output = QLabel("Output folder will be created inside the active project workspace.")
        bind_text(self.output, "generate.output.pending", self.tr)
        self.output.setObjectName("Muted")
        root.addWidget(self.output)
        root.addStretch()
        self.refresh_from_workspace()
        self.retranslate_ui()

    def _workspace(self) -> ProjectWorkspace | None:
        return self.workspace_provider()

    def start_generation(self) -> None:
        ws = self._workspace()
        if ws is None:
            QMessageBox.warning(self, self.tr.text("generate.project_required"), self.tr.text("cmip6.message.project_required.text"))
            return
        report = run_generation_preflight(ws, process_active=self.runner.is_running)
        self._render_preflight(report)
        if not report.passed:
            lines = []
            preflight_name_keys = {
                "project": "generate.preflight.project",
                "baseline": "generate.preflight.baseline",
                "location": "generate.preflight.location",
                "protocol": "generate.preflight.protocol",
                "selection": "generate.preflight.selection",
                "manifest": "generate.preflight.manifest",
                "cache": "generate.preflight.cache",
                "output": "generate.preflight.output",
                "idle": "generate.preflight.idle",
            }
            for check in report.failed_checks():
                stable = check.key or check.name.lower().replace(" ", "_")
                display_name = self.tr.text(preflight_name_keys.get(stable, check.name))
                detail = self.tr.text(f"preflight.{stable}.fail", detail=check.detail)
                recovery = self.tr.text(f"preflight.{stable}.recovery")
                lines.append(f"• {display_name}: {detail}\n  {recovery}")
            QMessageBox.warning(
                self,
                self.tr.text("generate.preflight_failed"),
                self.tr.text("generate.preflight_blocked") + "\n\n" + "\n".join(lines),
            )
            return

        store = WorkflowStateStore(ws)
        current = store.reconcile(active_process=False)
        store.save(replace(
            current, current_stage="stage03", state="running",
            generation_status="running", validation_status="not_started", last_error=None,
        ))
        commands = self.backend.commands(ws)
        steps = [
            ProcessStep("Stage 03 · climate factors", commands.stage03, self.backend.engine_dir, ws.logs_dir / "stage03.log"),
            ProcessStep("Stage 04 · generate EPW", commands.stage04, self.backend.engine_dir, ws.logs_dir / "stage04.log"),
            ProcessStep("Stage 05 · validate", commands.stage05, self.backend.engine_dir, ws.logs_dir / "stage05.log"),
        ]
        self.current_case.setText(self.tr.text("generate.stage03.start"))
        expected = ws.expected_epw_count()
        self.progress.setRange(0, max(1, expected))
        self.progress.setValue(0)
        self.generate_btn.setEnabled(False)
        if not self.runner.run_sequence(steps):
            self.generate_btn.setEnabled(True)
            store.save(replace(store.reconcile(active_process=False), state="ready"))
            QMessageBox.warning(self, self.tr.text("generate.message.busy.title"), self.tr.text("generate.message.busy.text"))
            return
        self.on_state_change()

    def refresh_from_workspace(self) -> None:
        ws = self._workspace()
        expected = ws.expected_epw_count() if ws is not None else expected_epw_count(self.state)
        self.expected_label.setText(f"{expected} EPW")
        if ws is None:
            self.generated_label.setText(f"0 / {expected}")
            self.progress.setRange(0, max(1, expected))
            self.progress.setValue(0)
            for name in self.preflight_labels:
                self._set_preflight(name, False)
            return
        WorkflowStateStore(ws).reconcile(active_process=self.runner.is_running)
        snap = ws.status_snapshot()
        self.state.factors_ready = snap.factors_ready
        self.state.fallback_rows = snap.fallback_rows
        self.state.generation_complete = snap.epw_count
        self.state.validation_passed = snap.validation_passed
        self.state.audit_groups = snap.audit_groups
        self.generated_label.setText(f"{snap.epw_count} / {expected}")
        self.progress.setRange(0, max(1, expected))
        self.progress.setValue(min(snap.epw_count, expected))
        self.output.setText(self.tr.text("generate.output.path", path=ws.epw_dir))
        self._render_preflight(run_generation_preflight(ws, process_active=self.runner.is_running))
        self._load_factor_metadata(ws)
        outcome = ws.validation_outcome()
        if outcome == "pass":
            self.current_case.setText(self.tr.text("status.pass"))
        elif outcome == "warning":
            self.current_case.setText(self.tr.text("status.pass_warnings"))
        elif outcome == "fail":
            self.current_case.setText(self.tr.text("status.fail"))
        self.on_state_change()

    def _load_factor_metadata(self, ws: ProjectWorkspace) -> None:
        import json
        if not ws.factor_metadata_file.exists():
            self.climatology_value.setText("—")
            self.per_gcm_value.setText("—")
            self.ensemble_value.setText("—")
            self.fallback_value.setText("—")
            self.warning_summary.setText(self.tr.text("generate.factor.none"))
            return
        data = json.loads(ws.factor_metadata_file.read_text(encoding="utf-8"))
        self.climatology_value.setText(f"{int(data.get('climatology_rows', 0)):,}")
        self.per_gcm_value.setText(f"{int(data.get('per_gcm_rows', 0)):,}")
        self.ensemble_value.setText(f"{int(data.get('ensemble_rows', 0)):,}")
        fallback = int(data.get("pr_dry_baseline_fallback_rows", 0))
        self.fallback_value.setText(self.tr.text("generate.factor.records", count=fallback))
        if fallback:
            self.warning_summary.setObjectName("Warning")
            self.warning_summary.setText(self.tr.text("generate.factor.fallback_yes", count=fallback))
        else:
            self.warning_summary.setObjectName("Success")
            self.warning_summary.setText(self.tr.text("generate.factor.fallback_no"))
        self.warning_summary.style().unpolish(self.warning_summary)
        self.warning_summary.style().polish(self.warning_summary)

    def _step_started(self, name: str) -> None:
        ws = self._workspace()
        stage = ""
        if name.startswith("Stage 03"):
            stage = "stage03"
            self.current_case.setText(self.tr.text("generate.stage03.running"))
        elif name.startswith("Stage 04"):
            stage = "stage04"
            self.current_case.setText(self.tr.text("generate.stage04.running"))
        elif name.startswith("Stage 05"):
            stage = "stage05"
            self.current_case.setText(self.tr.text("generate.stage05.running"))
        if ws is not None and stage:
            store = WorkflowStateStore(ws)
            current = store.load()
            store.save(replace(current, current_stage=stage, state="running"))

    def _step_finished(self, name: str, exit_code: int) -> None:
        if exit_code == 0 and name.startswith("Stage 03"):
            self.refresh_from_workspace()

    def _line_received(self, name: str, line: str) -> None:
        if name.startswith("Stage 04"):
            match = _GENERATE_RE.search(line)
            if match:
                idx, total, city, scenario, period, selector = match.groups()
                self.current_case.setText(f"{city} / {scenario.upper()} / {period} / {selector}")
                self.progress.setRange(0, int(total))
                self.progress.setValue(int(idx))
                self.generated_label.setText(f"{idx} / {total}")

    def _failure_reported(self, failure: ProcessFailure) -> None:
        if not failure.step_name.startswith(("Stage 03", "Stage 04", "Stage 05")):
            return
        self._last_failure = failure
        ws = self._workspace()
        if ws is None:
            return
        stage = "stage05" if failure.step_name.startswith("Stage 05") else ("stage04" if failure.step_name.startswith("Stage 04") else "stage03")
        code = "ValidationFailure" if stage == "stage05" else "BackendProcessFailure"
        message = "Scientific validation failed." if stage == "stage05" else f"Backend process failed during {failure.step_name}."
        store = WorkflowStateStore(ws)
        current = store.reconcile(active_process=False)
        store.save(replace(
            current, current_stage=stage, state="failed",
            generation_status="failed" if stage in {"stage03", "stage04"} else current.generation_status,
            validation_status="failed" if stage == "stage05" else current.validation_status,
            last_error={
                "code": code, "message": message, "exit_code": failure.exit_code,
                "log_file": failure.log_file, "recent_output": list(failure.last_lines),
            },
        ))

    def _sequence_finished(self, ok: bool, failed_step: str) -> None:
        self.generate_btn.setEnabled(True)
        ws = self._workspace()
        if ws is None:
            return
        record = WorkflowStateStore(ws).reconcile(active_process=False)
        self.refresh_from_workspace()
        generation_ok = ws.generation_complete()
        outcome = ws.validation_outcome()
        if ok and generation_ok and outcome in {"pass", "warning"}:
            label = self.tr.text("status.pass_warnings" if outcome == "warning" else "status.pass")
            QMessageBox.information(
                self,
                self.tr.text("generate.message.completed.title", status=label),
                self.tr.text("generate.message.completed.text", status=label, count=ws.expected_epw_count()),
            )
        else:
            if ok and not generation_ok:
                detail = self.tr.text("generate.message.artifacts_missing")
            elif ok and outcome == "fail":
                detail = self.tr.text("generate.message.validation_failed")
            elif self._last_failure is not None:
                recent = "\n".join(self._last_failure.last_lines[-6:])
                detail = (
                    self.tr.text("generate.message.backend_failed", step=failed_step)
                    + "\n\n" + self.tr.text("generate.message.recent_output") + "\n" + recent
                )
            else:
                detail = self.tr.text("generate.message.backend_failed", step=failed_step)
            log_path = self._last_failure.log_file if self._last_failure and self._last_failure.log_file else ws.logs_dir
            QMessageBox.critical(
                self,
                self.tr.text("status.fail"),
                detail + "\n\n" + self.tr.text("generate.message.see_logs", path=log_path),
            )
        self._last_failure = None
        self.on_state_change()

    def _show_factors(self) -> None:
        ws = self._workspace()
        if ws is None:
            QMessageBox.warning(self, self.tr.text("generate.project_required"), self.tr.text("generate.dialog.project_required.text"))
            return
        path = ws.factors_dir / "climate_factors_per_gcm.csv"
        if not path.exists():
            QMessageBox.information(self, self.tr.text("generate.dialog.factors.title"), self.tr.text("generate.dialog.factors.run_first"))
            return
        rows: list[dict[str, str]] = []
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if row.get("city") == ws.city and row.get("model") == self.state.gcms[0] and row.get("scenario") == self.state.scenarios[0] and row.get("target_label") == self.state.periods[0]:
                    rows.append(row)
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr.text("generate.dialog.factors.title"))
        dialog.resize(760, 420)
        layout = QVBoxLayout(dialog)
        table = QTableWidget(len(rows), 5)
        table.setHorizontalHeaderLabels([self.tr.text("generate.dialog.factors.month"), "ΔT (°C)", "huss ratio", "Wind ratio", "rsds Δ"])
        for r, row in enumerate(rows):
            values = [row.get("month", ""), row.get("d_tas", ""), row.get("r_huss", ""), row.get("r_wind", ""), row.get("d_rsds", "")]
            for c, value in enumerate(values):
                table.setItem(r, c, QTableWidgetItem(value))
        table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(table)
        dialog.exec()

    def _show_warning(self) -> None:
        ws = self._workspace()
        if ws is None:
            return
        fallback = ws.factors_dir / "precipitation_dry_baseline_fallbacks.csv"
        if not fallback.exists():
            QMessageBox.information(self, self.tr.text("generate.dialog.warnings.title"), self.tr.text("generate.dialog.warnings.none"))
            return
        with fallback.open("r", encoding="utf-8-sig", errors="replace") as handle:
            rows = max(0, sum(1 for _ in handle) - 1)
        QMessageBox.information(
            self,
            self.tr.text("generate.dialog.warnings.title"),
            self.tr.text("generate.dialog.warnings.records", count=rows, path=fallback),
        )

    def _open_folder(self) -> None:
        ws = self._workspace()
        if ws is None:
            QMessageBox.warning(self, self.tr.text("generate.project_required"), self.tr.text("generate.dialog.project_required.text"))
            return
        ws.epw_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(ws.epw_dir)))

    def _render_preflight(self, report) -> None:
        for check in report.checks:
            if check.name in self.preflight_labels:
                self._set_preflight(check.name, check.passed)

    def _set_preflight(self, key: str, passed: bool) -> None:
        pill = self.preflight_labels[key]
        pill.setText(self.tr.text("status.pass") if passed else self.tr.text("common.waiting"))
        pill.setProperty("statusKind", "complete" if passed else "pending")
        pill.style().unpolish(pill)
        pill.style().polish(pill)

    def retranslate_ui(self) -> None:
        retranslate_tree(self, self.tr)
        self.stop_btn.setToolTip(self.tr.text("generate.stop.tooltip"))
        self.refresh_from_workspace()
