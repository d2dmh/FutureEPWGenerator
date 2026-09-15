from __future__ import annotations

import csv
import json
import zipfile
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..demo_state import WorkflowState, validation_overall_status
from ..i18n import Translator, bind_text, retranslate_tree
from ..project_workspace import ProjectWorkspace
from ..widgets import data_panel, page_header, research_strip, status_pill


METHODS_SUMMARY = (
    "Future EPW files were generated using monthly CMIP6 climate signals from five GCMs under "
    "SSP1-2.6, SSP2-4.5, and SSP3-7.0. Historical climate signals used 1985–2014, while future "
    "conditions used 21-year windows centered on 2040 (2030–2050) and 2060 (2050–2070). "
    "The validated workflow uses bilinear spatial interpolation and variable-specific morphing, "
    "with documented fallback handling for near-zero baseline precipitation."
)


class ValidationPage(QWidget):
    def __init__(
        self,
        state: WorkflowState,
        workspace_provider: Callable[[], ProjectWorkspace | None],
        translator: Translator | None = None,
    ):
        super().__init__()
        self.state = state
        self.tr = translator or Translator()
        self.workspace_provider = workspace_provider

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 24)
        root.setSpacing(13)
        title, subtitle = page_header(
            "Validation & Export",
            "Quality assurance dashboard for physical validity, target agreement and reproducible research export",
            translator=self.tr,
            title_key="validation.title",
            subtitle_key="validation.subtitle",
        )
        root.addWidget(title)
        root.addWidget(subtitle)

        self.summary_strip = research_strip([
            ("Hard QA", "Live", "Loaded from Stage 05 metadata"),
            ("EPW files", "—", "Active project coverage"),
            ("Target agreement", "—", "Morphing target vs achieved"),
            ("Audit coverage", "—", "Post-serialization audit groups"),
        ])
        strip_keys = [
            ("validation.strip.hard", "validation.strip.hard.value", "validation.strip.hard.detail"),
            ("validation.strip.epw", None, "validation.strip.epw.detail"),
            ("validation.strip.target", None, "validation.strip.target.detail"),
            ("validation.strip.audit", None, "validation.strip.audit.detail"),
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

        overall, overall_layout = data_panel(
            "Quality assurance dashboard",
            "Hard QA determines usability; scientific warnings remain visible as provenance without being misclassified as failure.",
            translator=self.tr,
            title_key="validation.qa.title",
            subtitle_key="validation.qa.subtitle",
        )
        overall_top = QHBoxLayout()
        status_col = QVBoxLayout()
        self.status_label = QLabel(self.tr.text("validation.not_run"))
        self.status_label.setObjectName("LargeStatus")
        status_col.addWidget(self.status_label)
        self.active_project_label = QLabel(self.tr.text("validation.active.none"))
        self.active_project_label.setObjectName("Muted")
        status_col.addWidget(self.active_project_label)
        overall_top.addLayout(status_col, 2)
        overall_top.addStretch()
        self.hard_pill = status_pill(self.tr.text("validation.waiting"), "pending")
        self.warning_pill = status_pill(self.tr.text("validation.warnings", count=0), "pending")
        overall_top.addWidget(self.hard_pill)
        overall_top.addWidget(self.warning_pill)
        overall_layout.addLayout(overall_top)
        root.addWidget(overall)

        middle = QHBoxLayout()
        middle.setSpacing(13)
        qa, qa_layout = data_panel(
            "Hard QA",
            "Blocking checks are read from outputs/validation/validation_summary.csv.",
            translator=self.tr,
            title_key="validation.hard.title",
            subtitle_key="validation.hard.subtitle",
        )
        self.qa_values: dict[str, QLabel] = {}
        qa_rows = [
            ("File count", "validation.qa.file_count"),
            ("Hour count", "validation.qa.hour_count"),
            ("Missing values", "validation.qa.missing"),
            ("Physical bounds", "validation.qa.bounds"),
            ("Target vs achieved", "validation.qa.target"),
        ]
        for internal_key, text_key in qa_rows:
            row = QHBoxLayout()
            label = QLabel(internal_key)
            bind_text(label, text_key, self.tr)
            row.addWidget(label)
            row.addStretch()
            value = QLabel("—")
            value.setObjectName("Muted")
            self.qa_values[internal_key] = value
            row.addWidget(value)
            qa_layout.addLayout(row)
        middle.addWidget(qa, 3)

        provenance, provenance_layout = data_panel(
            "Scientific provenance",
            "Dry-baseline precipitation fallbacks remain explicit in the factor audit.",
            translator=self.tr,
            title_key="validation.provenance.title",
            subtitle_key="validation.provenance.subtitle",
        )
        self.provenance_pill = status_pill(self.tr.text("validation.no_data"), "pending")
        provenance_layout.addWidget(self.provenance_pill)
        self.warning = QLabel(self.tr.text("validation.provenance.none"))
        self.warning.setWordWrap(True)
        provenance_layout.addWidget(self.warning)
        middle.addWidget(provenance, 2)
        root.addLayout(middle)

        details, details_layout = data_panel(
            "Validation details",
            "Representative records read from the actual validation summary.",
            translator=self.tr,
            title_key="validation.details.title",
            subtitle_key="validation.details.subtitle",
        )
        self.table = QTableWidget(0, 5)
        self._set_table_headers()
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setMaximumHeight(210)
        details_layout.addWidget(self.table)
        root.addWidget(details)

        export, export_layout = data_panel(
            "Research export",
            "Package project metadata, manifests, factors, validation outputs and generated EPWs.",
            translator=self.tr,
            title_key="validation.export.title",
            subtitle_key="validation.export.subtitle",
        )
        actions = QHBoxLayout()
        open_epw = QPushButton("Open EPW Folder")
        bind_text(open_epw, "validation.button.epw", self.tr)
        open_epw.clicked.connect(self._open_epw)
        report = QPushButton("Open Validation Folder")
        bind_text(report, "validation.button.validation", self.tr)
        report.clicked.connect(self._open_validation)
        export_btn = QPushButton("Export Project Package")
        bind_text(export_btn, "validation.button.export", self.tr)
        export_btn.clicked.connect(self._export_project)
        copy = QPushButton("Copy Methods Summary")
        bind_text(copy, "validation.button.copy", self.tr)
        copy.setObjectName("PrimaryButton")
        copy.clicked.connect(self._copy_methods)
        for button in [open_epw, report, export_btn, copy]:
            actions.addWidget(button)
        actions.addStretch()
        export_layout.addLayout(actions)
        root.addWidget(export)
        root.addStretch()
        self.refresh()

    def _workspace(self) -> ProjectWorkspace | None:
        return self.workspace_provider()

    def refresh(self) -> None:
        ws = self._workspace()
        if ws is None:
            self.status_label.setText(self.tr.text("validation.not_run"))
            self.active_project_label.setText(self.tr.text("validation.active.none"))
            return
        snap = ws.status_snapshot()
        expected = ws.expected_epw_count()
        warnings = snap.fallback_rows
        outcome = ws.validation_outcome()
        passed = outcome in {"pass", "warning"}
        if outcome == "not_run":
            overall = self.tr.text("validation.not_run")
        elif outcome == "fail":
            overall = self.tr.text("status.fail")
        elif outcome == "warning":
            overall = self.tr.text("status.pass_warnings")
        else:
            # Keep the scientific state calculation centralized while localizing its presentation.
            overall_raw = validation_overall_status(hard_checks_pass=True, warning_count=warnings)
            overall = self.tr.text("status.pass_warnings" if "WARNING" in overall_raw else "status.pass")
        self.status_label.setText(overall)
        if outcome == "not_run":
            self.active_project_label.setText(self.tr.text("validation.active.missing"))
        else:
            self.active_project_label.setText(self.tr.text("validation.active.project", count=snap.epw_count, expected=expected))

        hard_text = (
            self.tr.text("validation.hard.pass") if passed
            else (self.tr.text("validation.hard.fail") if outcome == "fail" else self.tr.text("validation.waiting"))
        )
        hard_kind = "complete" if passed else ("warning" if outcome == "fail" else "pending")
        self._set_pill(self.hard_pill, hard_text, hard_kind)
        self._set_pill(
            self.warning_pill,
            self.tr.text("validation.warnings", count=warnings),
            "warning" if warnings else ("complete" if passed else "pending"),
        )

        file_count_complete = snap.epw_count == expected and outcome != "not_run"
        self.qa_values["File count"].setText(f"{snap.epw_count} / {expected}" if outcome != "not_run" else "—")
        self.qa_values["Hour count"].setText(self.tr.text("validation.hours_each") if passed and file_count_complete else "—")
        for key in ["Missing values", "Physical bounds", "Target vs achieved"]:
            if passed and file_count_complete:
                self.qa_values[key].setText(self.tr.text("common.pass"))
            elif outcome == "fail":
                self.qa_values[key].setText(self.tr.text("common.fail"))
            else:
                self.qa_values[key].setText("—")
        for key, label in self.qa_values.items():
            ok = (key == "File count" and file_count_complete) or (key != "File count" and passed and file_count_complete)
            label.setObjectName("Success" if ok else ("Warning" if outcome == "fail" else "Muted"))
            label.style().unpolish(label)
            label.style().polish(label)

        if ws.factor_metadata_file.exists():
            try:
                data = json.loads(ws.factor_metadata_file.read_text(encoding="utf-8"))
                fallback = int(data.get("pr_dry_baseline_fallback_rows", 0))
            except Exception:
                fallback = 0
            if fallback:
                self._set_pill(self.provenance_pill, self.tr.text("validation.provenance.documented"), "warning")
                self.warning.setText(self.tr.text("validation.provenance.warning", count=fallback, path=ws.factors_dir))
                self.warning.setObjectName("Warning")
            else:
                self._set_pill(self.provenance_pill, self.tr.text("validation.provenance.no_fallbacks"), "complete")
                self.warning.setText(self.tr.text("validation.provenance.clean"))
                self.warning.setObjectName("Success")
            self.warning.style().unpolish(self.warning)
            self.warning.style().polish(self.warning)
        else:
            self._set_pill(self.provenance_pill, self.tr.text("validation.no_data"), "pending")
            self.warning.setText(self.tr.text("validation.provenance.none"))
            self.warning.setObjectName("Muted")

        self._load_validation_table(ws)

    def _set_table_headers(self) -> None:
        self.table.setHorizontalHeaderLabels([
            self.tr.text("validation.table.file"),
            self.tr.text("validation.table.rows"),
            self.tr.text("validation.table.wmo"),
            self.tr.text("validation.table.latitude"),
            self.tr.text("validation.table.status"),
        ])

    def _load_validation_table(self, ws: ProjectWorkspace) -> None:
        path = ws.validation_dir / "validation_summary.csv"
        if not path.exists():
            self.table.setRowCount(0)
            return
        rows: list[dict[str, str]] = []
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
            reader = csv.DictReader(handle)
            rows.extend(reader)
        self.table.setRowCount(min(len(rows), 12))
        for r, row in enumerate(rows[:12]):
            passed = row.get("passed", "").lower() in {"true", "1"}
            values = [
                Path(row.get("file", "")).name,
                row.get("rows", ""),
                row.get("wmo", ""),
                row.get("latitude", ""),
                self.tr.text("common.pass" if passed else "common.fail"),
            ]
            for c, value in enumerate(values):
                self.table.setItem(r, c, QTableWidgetItem(value))

    def _copy_methods(self) -> None:
        # The copied methods paragraph remains English because it is intended for manuscript/report reuse;
        # only the application UI and confirmation message are localized.
        QApplication.clipboard().setText(METHODS_SUMMARY)
        QMessageBox.information(
            self,
            self.tr.text("validation.methods.copied.title"),
            self.tr.text("validation.methods.copied.text"),
        )

    def _open_epw(self) -> None:
        ws = self._workspace()
        if ws:
            ws.epw_dir.mkdir(parents=True, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(ws.epw_dir)))

    def _open_validation(self) -> None:
        ws = self._workspace()
        if ws:
            ws.validation_dir.mkdir(parents=True, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(ws.validation_dir)))

    def _export_project(self) -> None:
        ws = self._workspace()
        if ws is None:
            QMessageBox.warning(
                self,
                self.tr.text("validation.project_required.title"),
                self.tr.text("validation.project_required.text"),
            )
            return
        export_dir = ws.root / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        archive = export_dir / f"{ws.project_name}_research_export.zip"
        include = [ws.project_file, ws.manifest_dir, ws.factors_dir, ws.validation_dir, ws.epw_dir, ws.audit_dir]
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for item in include:
                if not item.exists():
                    continue
                if item.is_file():
                    zf.write(item, item.relative_to(ws.root))
                else:
                    for p in item.rglob("*"):
                        if p.is_file():
                            zf.write(p, p.relative_to(ws.root))
        QMessageBox.information(self, self.tr.text("validation.exported.title"), str(archive))

    def retranslate_ui(self) -> None:
        retranslate_tree(self, self.tr)
        self._set_table_headers()
        self.refresh()

    @staticmethod
    def _set_pill(widget: QLabel, text: str, kind: str) -> None:
        widget.setText(text)
        widget.setProperty("statusKind", kind)
        widget.style().unpolish(widget)
        widget.style().polish(widget)
