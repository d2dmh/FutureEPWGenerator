from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path
from typing import Callable

from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..backend import WorkflowBackend
from ..demo_state import WorkflowState
from ..eta import ExtractionETA, format_duration
from ..i18n import Translator, bind_text, retranslate_tree
from ..project_workspace import ProjectWorkspace
from ..runner import ProcessFailure, ProcessStep, WorkflowRunner
from ..workflow_state import WorkflowStateStore
from ..widgets import data_panel, page_header, status_pill


_PROGRESS_RE = re.compile(r"\[(\d+)/(\d+)\]\s+(?:cached\s+|asset complete\s+|extract\s+)?([^\s]+)?\s*([^\s]+)?\s*([^\s|]+)?")
_EXTRACT_RE = re.compile(
    r"\[(\d+)/(\d+)\]\s+extract\s+([^\s]+)\s+([^\s]+)\s+([^\s]+)\s+\|\s+city\s+(.+?)\s+\|\s+attempt\s+(\d+)/(\d+)"
)
_ASSET_COMPLETE_RE = re.compile(r"\[(\d+)/(\d+)\]\s+asset complete\s+([^\s]+)\s+([^\s]+)\s+([^\s]+)")
_CACHED_RE = re.compile(r"\[(\d+)/(\d+)\]\s+cached\s+([^\s]+)\s+([^\s]+)\s+([^\s]+)")


def _asset_id(model: str, scenario: str, variable: str) -> str:
    return f"{model}|{scenario}|{variable}"


class CMIP6Page(QWidget):
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
        self.eta = ExtractionETA()
        self._last_failure: ProcessFailure | None = None

        self.runner.step_started.connect(self._step_started)
        self.runner.line_received.connect(self._line_received)
        self.runner.step_finished.connect(self._step_finished)
        self.runner.sequence_finished.connect(self._sequence_finished)
        self.runner.failure_reported.connect(self._failure_reported)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 24)
        root.setSpacing(13)
        title, subtitle = page_header(
            "CMIP6 Data",
            "Extract city-scale monthly climate signals with auditable cache and provider telemetry",
            translator=self.tr,
            title_key="cmip6.title",
            subtitle_key="cmip6.subtitle",
        )
        root.addWidget(title)
        root.addWidget(subtitle)

        strip = QFrame()
        strip.setObjectName("ResearchStrip")
        strip_layout = QHBoxLayout(strip)
        strip_layout.setContentsMargins(0, 0, 0, 0)
        strip_layout.setSpacing(0)
        strip_specs = [
            ("cmip6.strip.assets", "cmip6.strip.assets.value", "cmip6.strip.assets.detail"),
            ("cmip6.strip.city_slots", "cmip6.strip.city_slots.value", "cmip6.strip.city_slots.detail"),
            ("cmip6.strip.variables", "cmip6.strip.variables.value", "cmip6.strip.variables.detail"),
            ("cmip6.strip.provider", "cmip6.strip.provider.value", "cmip6.strip.provider.detail"),
        ]
        for key, value_key, detail_key in strip_specs:
            from ..widgets import metric_cell
            cell = metric_cell(self.tr.text(key), self.tr.text(value_key), self.tr.text(detail_key))
            labels = cell.findChildren(QLabel)
            if len(labels) >= 3:
                bind_text(labels[0], key, self.tr)
                if key == "cmip6.strip.assets":
                    self.asset_strip_value = labels[1]
                    self.asset_strip_detail = labels[2]
                elif key == "cmip6.strip.city_slots":
                    self.city_slots_strip_value = labels[1]
                    self.city_slots_strip_detail = labels[2]
                else:
                    bind_text(labels[1], value_key, self.tr)
                    bind_text(labels[2], detail_key, self.tr)
            strip_layout.addWidget(cell, 1)
        root.addWidget(strip)

        telemetry, telemetry_layout = data_panel(
            "Extraction telemetry",
            "Real Stage 00–02 execution. Asset and city caches remain resumable across restarts.",
            translator=self.tr,
            title_key="cmip6.telemetry",
            subtitle_key="cmip6.telemetry.subtitle",
        )
        overall_label = QLabel("Overall Progress")
        overall_label.setObjectName("TinyLabel")
        bind_text(overall_label, "cmip6.progress.overall", self.tr)
        telemetry_layout.addWidget(overall_label)
        tele_top = QHBoxLayout()
        percent_col = QVBoxLayout()
        self.percent = QLabel("0%")
        self.percent.setObjectName("PercentValue")
        initial_total = max(1, int(state.cmip6_total))
        self.progress_text = QLabel(self.tr.text("cmip6.progress.assets_cached", complete=0, total=initial_total))
        self.progress_text.setObjectName("Muted")
        percent_col.addWidget(self.percent)
        percent_col.addWidget(self.progress_text)
        tele_top.addLayout(percent_col)
        tele_top.addStretch()
        self.task_status = status_pill(self.tr.text("cmip6.task.ready"), "info")
        tele_top.addWidget(self.task_status)
        telemetry_layout.addLayout(tele_top)
        self.progress = QProgressBar()
        self.progress.setRange(0, state.cmip6_total)
        telemetry_layout.addWidget(self.progress)

        task_grid = QGridLayout()
        task_grid.setHorizontalSpacing(18)
        task_grid.setVerticalSpacing(4)
        self.model = QLabel("—")
        self.scenario = QLabel("—")
        self.variable = QLabel("—")
        self.city = QLabel(state.city_name)
        self.provider = QLabel(state.active_provider)
        self.attempt = QLabel("—")
        fields = [
            ("cmip6.field.model", self.model, "MODEL"),
            ("cmip6.field.scenario", self.scenario, "SCENARIO"),
            ("cmip6.field.variable", self.variable, "VARIABLE"),
            ("cmip6.field.city", self.city, "CITY"),
            ("cmip6.field.provider", self.provider, "PROVIDER"),
            ("cmip6.field.attempt", self.attempt, "ATTEMPT"),
        ]
        for col, (key, widget, original) in enumerate(fields):
            lab = QLabel(original)
            bind_text(lab, key, self.tr)
            lab.setObjectName("TinyLabel")
            widget.setObjectName("MonoValue" if original in {"MODEL", "VARIABLE", "PROVIDER"} else "MetaValue")
            task_grid.addWidget(lab, 0, col)
            task_grid.addWidget(widget, 1, col)
            task_grid.setColumnStretch(col, 1)
        telemetry_layout.addLayout(task_grid)

        controls = QHBoxLayout()
        self.pause_btn = QPushButton("Pause")
        bind_text(self.pause_btn, "cmip6.button.pause", self.tr)
        self.resume_btn = QPushButton("Start / Resume")
        bind_text(self.resume_btn, "cmip6.button.start", self.tr)
        self.retry_btn = QPushButton("Retry Failed")
        bind_text(self.retry_btn, "cmip6.button.retry", self.tr)
        self.status_btn = QPushButton("Check Status")
        bind_text(self.status_btn, "cmip6.button.status", self.tr)
        self.pause_btn.clicked.connect(self.pause)
        self.resume_btn.clicked.connect(self.resume)
        self.retry_btn.clicked.connect(self.retry_failed)
        self.status_btn.clicked.connect(self.check_status)
        for button in [self.resume_btn, self.pause_btn, self.retry_btn, self.status_btn]:
            controls.addWidget(button)
        controls.addStretch()
        self.data_transfer = QLabel("Real engine  ·  GCS primary / AWS fallback  ·  300 s city timeout")
        bind_text(self.data_transfer, "cmip6.transfer", self.tr)
        self.data_transfer.setObjectName("Muted")
        controls.addWidget(self.data_transfer)
        telemetry_layout.addLayout(controls)
        root.addWidget(telemetry)

        middle = QHBoxLayout()
        middle.setSpacing(13)
        cache_panel, cache_layout = data_panel(
            "Scientific cache",
            "Project-local caches use the same schema as the validated command-line workflow.",
            translator=self.tr,
            title_key="cmip6.cache.title",
            subtitle_key="cmip6.cache.subtitle",
        )
        cache_grid = QGridLayout()
        self.complete_label = QLabel("0")
        self.pending_label = QLabel(str(initial_total))
        self.failed_label = QLabel("0")
        self.checkpoint_label = QLabel("0")
        self.remote_ready_label = QLabel(f"0 / {initial_total}")
        cache_items = [
            ("cmip6.cache.complete", self.complete_label, "COMPLETE"),
            ("cmip6.cache.pending", self.pending_label, "PENDING"),
            ("cmip6.cache.failed", self.failed_label, "FAILED"),
            ("cmip6.cache.checkpoints", self.checkpoint_label, "CITY CHECKPOINTS"),
            ("cmip6.cache.remote_ready", self.remote_ready_label, "REMOTE DATA READY"),
        ]
        for i, (key, value, original) in enumerate(cache_items):
            row, col = divmod(i, 2)
            name_label = QLabel(original)
            bind_text(name_label, key, self.tr)
            name_label.setObjectName("TinyLabel")
            value.setObjectName("QaValue")
            cache_grid.addWidget(name_label, row * 2, col)
            cache_grid.addWidget(value, row * 2 + 1, col)
        cache_layout.addLayout(cache_grid)
        middle.addWidget(cache_panel, 1)

        provider_panel, provider_layout = data_panel(
            "Remote provider",
            "Provider fallback is surfaced because it is part of retrieval provenance.",
            translator=self.tr,
            title_key="cmip6.provider.title",
            subtitle_key="cmip6.provider.subtitle",
        )
        self.gcs_label = QLabel("GCS     Primary")
        self.aws_label = QLabel("AWS     Standby")
        self.project_path_label = QLabel(self.tr.text("cmip6.project_cache_uninitialized"))
        self.project_path_label.setWordWrap(True)
        self.project_path_label.setObjectName("Muted")
        provider_layout.addWidget(self.gcs_label)
        provider_layout.addWidget(self.aws_label)
        provider_layout.addSpacing(4)
        provider_layout.addWidget(self.project_path_label)
        middle.addWidget(provider_panel, 1)
        root.addLayout(middle)

        eta_panel, eta_layout = data_panel(
            "Estimated remaining",
            "",
            translator=self.tr,
            title_key="cmip6.eta.title",
        )
        eta_row = QHBoxLayout()
        self.eta_value = QLabel(self.tr.text("cmip6.eta.estimating"))
        self.eta_value.setObjectName("QaValue")
        self.eta_typical = QLabel("—")
        self.eta_typical.setObjectName("Muted")
        self.eta_remote_left = QLabel(self.tr.text("cmip6.eta.remote_left", count=initial_total))
        self.eta_remote_left.setObjectName("Muted")
        eta_col = QVBoxLayout()
        eta_col.addWidget(self.eta_value)
        eta_col.addWidget(self.eta_typical)
        eta_row.addLayout(eta_col, 1)
        eta_row.addWidget(self.eta_remote_left)
        eta_layout.addLayout(eta_row)
        root.addWidget(eta_panel)

        activity_panel, activity_layout = data_panel(
            "Recent activity",
            "Live stdout from the validated workflow is captured to project logs and optionally shown here.",
            translator=self.tr,
            title_key="cmip6.recent.title",
            subtitle_key="cmip6.recent.subtitle",
        )
        self.activity = QListWidget()
        self.activity.setObjectName("ActivityList")
        self.activity.setMaximumHeight(112)
        activity_layout.addWidget(self.activity)
        self.log_toggle = QPushButton("Show detailed log")
        self.log_toggle.setCheckable(True)
        self.log_toggle.toggled.connect(self._toggle_log)
        activity_layout.addWidget(self.log_toggle)
        self.log = QTextEdit()
        self.log.setObjectName("LogConsole")
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(170)
        self.log.hide()
        activity_layout.addWidget(self.log)
        root.addWidget(activity_panel)
        root.addStretch()
        self.refresh_from_workspace()
        self.retranslate_ui()

    def _workspace(self) -> ProjectWorkspace | None:
        return self.workspace_provider()

    def _require_workspace(self) -> ProjectWorkspace | None:
        ws = self._workspace()
        if ws is None:
            QMessageBox.warning(
                self,
                self.tr.text("cmip6.message.project_required.title"),
                self.tr.text("cmip6.message.project_required.text"),
            )
        return ws

    def resume(self) -> None:
        ws = self._require_workspace()
        if ws is None:
            return
        if self.runner.is_running:
            QMessageBox.information(
                self,
                self.tr.text("cmip6.message.busy.title"),
                self.tr.text("cmip6.message.currently_running", step=self.runner.current_step_name),
            )
            return
        store = WorkflowStateStore(ws)
        current = store.reconcile(active_process=False)
        store.save(replace(current, current_stage="stage02", state="running", last_error=None))
        self.backend.clear_pause_request(ws)
        commands = self.backend.commands(ws)
        steps: list[ProcessStep] = []
        env_report = ws.outputs_dir / "environment_report.json"
        env_ok = False
        if env_report.exists():
            try:
                env_ok = bool(json.loads(env_report.read_text(encoding="utf-8")).get("passed", False))
            except Exception:
                env_ok = False
        if not env_ok:
            steps.append(ProcessStep("Stage 00 · environment", commands.stage00, self.backend.engine_dir, ws.logs_dir / "stage00.log"))
        if not ws.manifest_matches_selection():
            steps.append(ProcessStep("Stage 01 · manifest", commands.stage01, self.backend.engine_dir, ws.logs_dir / "stage01.log"))
        steps.extend([
            ProcessStep("Stage 02 · CMIP6 extraction", commands.stage02, self.backend.engine_dir, ws.logs_dir / "stage02.log"),
            ProcessStep("Stage 02 · status", commands.stage02_status, self.backend.engine_dir, ws.logs_dir / "stage02_status.log"),
        ])
        self.state.resume_cmip6()
        self.eta.resume()
        self.task_status.setText(self.tr.text("cmip6.task.running"))
        self._repolish(self.task_status, "info")
        self._append_log("Starting real CMIP6 workflow sequence")
        if not self.runner.run_sequence(steps):
            QMessageBox.warning(self, self.tr.text("cmip6.message.busy.title"), self.tr.text("cmip6.message.busy.text"))
        self.on_state_change()

    def pause(self) -> None:
        ws = self._require_workspace()
        if ws is None:
            return
        if not self.runner.is_running:
            QMessageBox.information(
                self,
                self.tr.text("cmip6.message.not_running.title"),
                self.tr.text("cmip6.message.not_running.text"),
            )
            return
        store = WorkflowStateStore(ws)
        current = store.load()
        store.save(replace(current, current_stage="stage02", state="pausing"))
        remaining_remote = max(0, self.state.cmip6_total - self.state.remote_ready)
        self.eta.pause(remaining_remote=remaining_remote)
        self.backend.request_pause(ws)
        self.task_status.setText(self.tr.text("cmip6.task.pausing"))
        self._repolish(self.task_status, "pending")
        self._append_log("Pause requested; current city operation will finish and caches will be preserved.")
        self._refresh_eta()

    def retry_failed(self) -> None:
        self.refresh_from_workspace()
        self.resume()

    def check_status(self) -> None:
        ws = self._require_workspace()
        if ws is None:
            return
        if not ws.manifest_matches_selection():
            QMessageBox.information(
                self,
                self.tr.text("cmip6.message.manifest.title"),
                self.tr.text("cmip6.message.manifest.text"),
            )
            return
        if self.runner.is_running:
            QMessageBox.information(
                self,
                self.tr.text("cmip6.message.busy.title"),
                self.tr.text("cmip6.message.currently_running", step=self.runner.current_step_name),
            )
            return
        cmd = self.backend.commands(ws).stage02_status
        self.runner.run_sequence([ProcessStep("Stage 02 · status", cmd, self.backend.engine_dir, ws.logs_dir / "stage02_status.log")])

    def refresh_from_workspace(self) -> None:
        ws = self._workspace()
        if ws is None:
            self._refresh_widgets()
            return
        record = WorkflowStateStore(ws).reconcile(active_process=self.runner.is_running)
        snap = ws.status_snapshot()
        self.state.cmip6_total = snap.cmip6_total
        self.state.cmip6_complete = snap.cmip6_complete
        self.state.city_cached = snap.city_cached
        self.state.remote_ready = snap.remote_ready
        self.state.factors_ready = snap.factors_ready
        self.state.fallback_rows = snap.fallback_rows
        self.state.generation_complete = snap.epw_count
        self.state.validation_passed = snap.validation_passed
        self.state.audit_groups = snap.audit_groups
        self.state.cmip6_running = record.state in {"running", "pausing"}
        self.state.cmip6_failed = 1 if record.state == "failed" and record.current_stage == "stage02" else 0
        self.city.setText(ws.city)
        self.project_path_label.setText(self.tr.text("cmip6.project_cache", path=ws.cache_dir))
        self._refresh_widgets()

    def _step_started(self, name: str) -> None:
        if not name.startswith("Stage 0"):
            return
        stage = "stage02"
        if name.startswith("Stage 00"):
            stage = "stage00"
        elif name.startswith("Stage 01"):
            stage = "stage01"
        ws = self._workspace()
        if ws is not None:
            store = WorkflowStateStore(ws)
            current = store.load()
            store.save(replace(current, current_stage=stage, state="running"))
        self._append_log(f"▶ {name}")
        if "Stage 02" in name:
            self.task_status.setText(self.tr.text("cmip6.task.running"))
            self._repolish(self.task_status, "info")

    def _step_finished(self, name: str, exit_code: int) -> None:
        if name.startswith("Stage 0"):
            self._append_log(f"■ {name} finished rc={exit_code}")

    def _line_received(self, name: str, line: str) -> None:
        if not name.startswith("Stage 0"):
            return
        if line.strip():
            self._append_log(line)
        lower = line.lower()

        new_provider: str | None = None
        if "provider=aws" in lower or "[aws]" in lower:
            new_provider = "AWS"
            self.state.gcs_status = "Fallback"
            self.state.aws_status = "Active"
        elif "provider=gcs" in lower or "[gcs]" in lower:
            new_provider = "GCS"
        if new_provider is not None and new_provider != self.state.active_provider:
            self.eta.change_provider(new_provider)
            self.state.active_provider = new_provider

        match = _EXTRACT_RE.search(line)
        if match:
            _pos, _total, model, scenario, variable, city, attempt, attempts = match.groups()
            self.model.setText(model)
            self.scenario.setText(scenario.upper())
            self.variable.setText(variable)
            self.city.setText(city)
            self.attempt.setText(f"{attempt} / {attempts}")
            self.eta.start_asset(_asset_id(model, scenario, variable), self.state.active_provider)

        complete_match = _ASSET_COMPLETE_RE.search(line)
        cached_match = _CACHED_RE.search(line)
        if complete_match:
            _pos, _total, model, scenario, variable = complete_match.groups()
            self.eta.finish_asset(_asset_id(model, scenario, variable), self.state.active_provider, genuine_remote=True)
            self.state.recent_activity.insert(0, line.strip())
            self.state.recent_activity = self.state.recent_activity[:8]
            self.refresh_from_workspace()
        elif cached_match:
            # Cache hits are scientific progress but must not contaminate remote ETA speed.
            self.state.recent_activity.insert(0, line.strip())
            self.state.recent_activity = self.state.recent_activity[:8]
            self.refresh_from_workspace()
        else:
            self.provider.setText(self.state.active_provider)
            self._refresh_provider_labels()
            self._refresh_eta()

    def _failure_reported(self, failure: ProcessFailure) -> None:
        if not failure.step_name.startswith("Stage 0"):
            return
        self._last_failure = failure
        ws = self._workspace()
        if ws is None:
            return
        recent = "\n".join(failure.last_lines).lower()
        network_tokens = ("gcs", "aws", "timeout", "network", "ssl", "connection", "provider")
        code = "NetworkProviderFailure" if any(token in recent for token in network_tokens) else "BackendProcessFailure"
        message = (
            "CMIP6 data could not be retrieved from the configured providers."
            if code == "NetworkProviderFailure"
            else f"Backend process failed during {failure.step_name}."
        )
        stage = "stage02"
        if failure.step_name.startswith("Stage 00"):
            stage = "stage00"
        elif failure.step_name.startswith("Stage 01"):
            stage = "stage01"
        store = WorkflowStateStore(ws)
        current = store.reconcile(active_process=False)
        store.save(replace(
            current,
            current_stage=stage,
            state="failed",
            last_error={
                "code": code,
                "message": message,
                "exit_code": failure.exit_code,
                "log_file": failure.log_file,
                "recent_output": list(failure.last_lines),
            },
        ))

    def _sequence_finished(self, ok: bool, failed_step: str) -> None:
        ws = self._workspace()
        if ws is None:
            return
        self.state.pause_cmip6()
        store = WorkflowStateStore(ws)
        record = store.reconcile(active_process=False)
        self.refresh_from_workspace()
        if ws.stop_file.exists() and record.cmip6_complete < record.cmip6_total:
            paused = replace(record, current_stage="stage02", state="paused")
            store.save(paused)
            self.task_status.setText(self.tr.text("cmip6.task.paused"))
            self._repolish(self.task_status, "pending")
            self.eta.pause(remaining_remote=max(0, self.state.cmip6_total - self.state.remote_ready))
        elif ok:
            if self.state.cmip6_complete >= self.state.cmip6_total:
                self.task_status.setText(self.tr.text("cmip6.task.complete"))
                self._repolish(self.task_status, "complete")
            else:
                self.task_status.setText(self.tr.text("cmip6.task.ready"))
                self._repolish(self.task_status, "info")
        else:
            self.task_status.setText(self.tr.text("cmip6.task.failed"))
            self._repolish(self.task_status, "warning")
            self.state.last_error = failed_step
            failure = self._last_failure
            if failure is not None:
                recent = "\n".join(failure.last_lines[-6:])
                detail = f"\n\nRecent output:\n{recent}" if recent else ""
                log = failure.log_file or str(ws.logs_dir)
                body = self.tr.text("cmip6.message.failure.preserved", step=failed_step)
                body += "\n\n" + self.tr.text("cmip6.message.failure.log", path=log)
                if recent:
                    body += "\n\n" + self.tr.text("cmip6.message.failure.recent") + "\n" + recent
                QMessageBox.critical(
                    self,
                    self.tr.text("cmip6.message.workflow_failed.title"),
                    body,
                )
            else:
                QMessageBox.critical(
                    self,
                    self.tr.text("cmip6.message.workflow_failed.title"),
                    self.tr.text("cmip6.message.failure.see", step=failed_step, path=ws.logs_dir),
                )
        self._last_failure = None
        self._refresh_eta()
        self.on_state_change()

    def _refresh_widgets(self) -> None:
        complete = int(self.state.cmip6_complete)
        total = max(1, int(self.state.cmip6_total))
        pct = int(round(100 * complete / total))
        self.progress.setMaximum(total)
        self.progress.setValue(complete)
        self.percent.setText(f"{pct}%")
        self.progress_text.setText(self.tr.text("cmip6.progress.assets_cached", complete=complete, total=total))
        self.complete_label.setText(str(complete))
        self.pending_label.setText(str(max(0, total - complete)))
        self.failed_label.setText(str(self.state.cmip6_failed))
        self.checkpoint_label.setText(str(self.state.city_cached))
        self.remote_ready_label.setText(f"{self.state.remote_ready} / {total}")
        mode_key = "cmip6.mode.advanced" if getattr(self.state, "climate_mode", "reproducible") == "advanced" else "cmip6.mode.reproducible"
        mode_text = self.tr.text(mode_key)
        if hasattr(self, "asset_strip_value"):
            self.asset_strip_value.setText(self.tr.text("cmip6.strip.assets.dynamic_value", total=total))
            self.asset_strip_detail.setText(self.tr.text("cmip6.strip.assets.dynamic_detail", mode=mode_text))
        if hasattr(self, "city_slots_strip_value"):
            self.city_slots_strip_value.setText(f"1 × {total}")
            self.city_slots_strip_detail.setText(self.tr.text("cmip6.strip.city_slots.dynamic_detail"))
        self.provider.setText(self.state.active_provider)
        self._refresh_provider_labels()
        self.activity.clear()
        self.activity.addItems(self.state.recent_activity[:5])
        self._refresh_eta()
        self.on_state_change()

    def _refresh_eta(self) -> None:
        total = max(1, int(self.state.cmip6_total))
        remaining_remote = max(0, total - int(self.state.remote_ready))
        estimate = self.eta.estimate(remaining_remote)
        self.eta_remote_left.setText(self.tr.text("cmip6.eta.remote_left", count=remaining_remote))
        if not estimate.ready:
            self.eta_value.setText(self.tr.text("cmip6.eta.estimating"))
            self.eta_typical.setText("—")
            return
        self.eta_value.setText(self.tr.text("cmip6.eta.remaining", duration=format_duration(estimate.remaining_seconds, language=self.tr.language)))
        self.eta_typical.setText(self.tr.text("cmip6.eta.typical", seconds=estimate.seconds_per_asset or 0.0))

    def _refresh_provider_labels(self) -> None:
        status_key = {
            "Primary": "cmip6.provider.primary",
            "Standby": "cmip6.provider.standby",
            "Fallback": "cmip6.provider.fallback",
            "Active": "cmip6.provider.active",
            "Timeout": "cmip6.provider.timeout",
            "Active fallback": "cmip6.provider.active",
        }
        gcs = self.tr.text(status_key.get(self.state.gcs_status, "cmip6.provider.primary"))
        aws = self.tr.text(status_key.get(self.state.aws_status, "cmip6.provider.standby"))
        self.gcs_label.setText(f"GCS     {gcs}")
        self.aws_label.setText(f"AWS     {aws}")

    def set_default_log_visibility(self, visible: bool) -> None:
        self.log_toggle.setChecked(bool(visible))
        self._toggle_log(bool(visible))

    def _toggle_log(self, visible: bool) -> None:
        self.log.setVisible(visible)
        self.log_toggle.setText(self.tr.text("cmip6.log.hide" if visible else "cmip6.log.show"))

    def _append_log(self, message: str) -> None:
        self.log.append(message)

    def retranslate_ui(self) -> None:
        retranslate_tree(self, self.tr)
        self._toggle_log(self.log.isVisible())
        self._refresh_provider_labels()
        self._refresh_widgets()

    @staticmethod
    def _repolish(widget: QLabel, kind: str) -> None:
        widget.setProperty("statusKind", kind)
        widget.style().unpolish(widget)
        widget.style().polish(widget)
