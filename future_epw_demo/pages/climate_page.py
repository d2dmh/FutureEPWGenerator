from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QPushButton, QRadioButton, QVBoxLayout, QWidget, QMessageBox,
)

from ..demo_state import WorkflowState, configuration_fingerprint, expected_epw_count, dynamic_asset_total, DEFAULT_SCENARIOS, DEFAULT_PERIODS, DEFAULT_GCMS
from ..i18n import Translator, bind_text, retranslate_tree
from ..widgets import data_panel, metric_cell, page_header, status_pill

SCENARIO_LABELS = {"ssp126": "SSP1-2.6", "ssp245": "SSP2-4.5", "ssp370": "SSP3-7.0"}
PERIOD_LABELS = {"2040": "2040  (2030–2050)", "2060": "2060  (2050–2070)"}
RECOMMENDED_GCMS = ["ACCESS-CM2", "GFDL-ESM4", "MPI-ESM1-2-HR", "IPSL-CM6A-LR", "FGOALS-g3"]


class ClimatePage(QWidget):
    def __init__(self, state: WorkflowState, on_next: Callable[[], None], on_back: Callable[[], None], on_config_saved: Callable[[], None] | None = None, translator: Translator | None = None):
        super().__init__()
        self.state = state
        self.tr = translator or Translator()
        self.on_next = on_next
        self.on_back = on_back
        self.on_config_saved = on_config_saved or (lambda: None)
        self.scenario_checks: dict[str, QCheckBox] = {}
        self.period_checks: dict[str, QCheckBox] = {}
        self.gcm_checks: dict[str, QCheckBox] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 24)
        root.setSpacing(13)
        title, subtitle = page_header(
            "Climate Settings",
            "Define the CMIP6 experiment matrix and lock the validated morphing protocol",
            translator=self.tr,
            title_key="climate.title",
            subtitle_key="climate.subtitle",
        )
        root.addWidget(title)
        root.addWidget(subtitle)

        strip = QFrame(); strip.setObjectName("ResearchStrip")
        strip_layout = QHBoxLayout(strip); strip_layout.setContentsMargins(0,0,0,0); strip_layout.setSpacing(0)
        specs = [
            ("climate.strip.scenarios", "climate.strip.scenarios.value", "climate.strip.scenarios.detail"),
            ("climate.strip.time_slices", "climate.strip.time_slices.value", "climate.strip.time_slices.detail"),
            ("climate.strip.ensemble", "climate.strip.ensemble.value", "climate.strip.ensemble.detail"),
            ("climate.strip.expected", "climate.strip.expected.value", "climate.strip.expected.detail"),
        ]
        self.summary_strip_labels: dict[str, tuple[QLabel, QLabel]] = {}
        for key, value_key, detail_key in specs:
            cell = metric_cell(self.tr.text(key), self.tr.text(value_key), self.tr.text(detail_key))
            labels = cell.findChildren(QLabel)
            if len(labels) >= 3:
                bind_text(labels[0], key, self.tr)
                self.summary_strip_labels[key] = (labels[1], labels[2])
            strip_layout.addWidget(cell, 1)
        self.research_summary = strip
        root.addWidget(strip)

        upper = QHBoxLayout(); upper.setSpacing(13)
        matrix, matrix_layout = data_panel(
            "Climate experiment matrix",
            "Selections remain intentionally constrained in Reproducible Mode to preserve study comparability.",
            translator=self.tr, title_key="climate.matrix.title", subtitle_key="climate.matrix.subtitle",
        )
        matrix_grid = QGridLayout(); matrix_grid.setHorizontalSpacing(22); matrix_grid.setVerticalSpacing(5)
        matrix_grid.addWidget(self._eyebrow("FORCING PATHWAYS", "climate.matrix.forcing"), 0, 0)
        for row, (key, label) in enumerate(SCENARIO_LABELS.items(), start=1):
            cb = QCheckBox(label); cb.setChecked(key in state.scenarios); cb.toggled.connect(self._sync_state)
            self.scenario_checks[key] = cb; matrix_grid.addWidget(cb, row, 0)
        matrix_grid.addWidget(self._eyebrow("FUTURE WINDOWS", "climate.matrix.windows"), 0, 1)
        for row, (key, label) in enumerate(PERIOD_LABELS.items(), start=1):
            cb = QCheckBox(label); cb.setChecked(key in state.periods); cb.toggled.connect(self._sync_state)
            self.period_checks[key] = cb; matrix_grid.addWidget(cb, row, 1)
        matrix_grid.addWidget(self._eyebrow("GCM ENSEMBLE", "climate.matrix.gcm"), 0, 2)
        for row, model in enumerate(RECOMMENDED_GCMS, start=1):
            cb = QCheckBox(model); cb.setChecked(model in state.gcms); cb.toggled.connect(self._sync_state)
            self.gcm_checks[model] = cb; matrix_grid.addWidget(cb, row, 2)
        matrix_grid.setColumnStretch(0,1); matrix_grid.setColumnStretch(1,1); matrix_grid.setColumnStretch(2,2)
        matrix_layout.addLayout(matrix_grid); upper.addWidget(matrix, 5)

        design, design_layout = data_panel(
            "Experiment design", "Validated configuration used by the current production workflow.",
            translator=self.tr, title_key="climate.design.title", subtitle_key="climate.design.subtitle",
        )
        self.recommended = QRadioButton("Recommended / Reproducible Mode"); bind_text(self.recommended, "climate.mode.recommended", self.tr)
        self.advanced = QRadioButton("Advanced Mode"); bind_text(self.advanced, "climate.mode.advanced", self.tr)
        self.recommended.setChecked(state.climate_mode != "advanced")
        self.advanced.setChecked(state.climate_mode == "advanced")
        mode_group = QButtonGroup(self); mode_group.addButton(self.recommended); mode_group.addButton(self.advanced)
        design_layout.addWidget(self.recommended); design_layout.addWidget(self.advanced)
        self.advanced.toggled.connect(self._update_mode)
        self.recommended.toggled.connect(self._update_mode)
        self.advanced_note = QLabel("Advanced settings may reduce comparability with the validated reproducible workflow. Advanced mode runs only the selected validated CMIP6 subset in v0.9.2; the validated model set is unchanged.")
        bind_text(self.advanced_note, "climate.mode.advanced_note", self.tr)
        self.advanced_note.setObjectName("Warning"); self.advanced_note.setWordWrap(True); self.advanced_note.hide()
        design_layout.addWidget(self.advanced_note); design_layout.addSpacing(5)
        design_layout.addWidget(self._eyebrow("CONFIGURATION FINGERPRINT", "climate.fingerprint"))
        self.fingerprint = QLabel(); self.fingerprint.setObjectName("MonoValue"); self.fingerprint.setWordWrap(True)
        design_layout.addWidget(self.fingerprint)
        self.protocol_pill = status_pill("Validated protocol", "complete"); self.protocol_pill.setProperty("i18nKey", "climate.validated_protocol")
        design_layout.addWidget(self.protocol_pill); design_layout.addStretch(); upper.addWidget(design, 3)
        root.addLayout(upper)

        method, method_layout = data_panel(
            "Method specification",
            "Variable-specific morphing choices are visible here for auditability but locked in Reproducible Mode.",
            translator=self.tr, title_key="climate.method.title", subtitle_key="climate.method.subtitle",
        )
        method_grid = QGridLayout(); method_grid.setHorizontalSpacing(22); method_grid.setVerticalSpacing(0)
        left = [
            ("climate.method.historical", "Historical reference", "1985–2014"),
            ("climate.method.future", "Future windows", "21-year centered climatology"),
            ("climate.method.spatial", "Spatial interpolation", "Bilinear"),
            ("climate.method.temperature", "Temperature", "BTWS"),
            ("climate.method.solar", "Solar / cloud", "BWS"),
        ]
        right = [
            ("climate.method.humidity", "Humidity", "huss-based"),
            ("climate.method.pressure", "Pressure", "psl"),
            ("climate.method.wind", "Wind", "sfcWind ratio"),
            ("climate.method.precip", "Precipitation", "pr ratio + dry-baseline fallback"),
            ("climate.method.ensemble", "Ensemble", "5-model mean"),
        ]
        for row, triple in enumerate(left): method_grid.addWidget(self._method_row(*triple), row, 0)
        for row, triple in enumerate(right): method_grid.addWidget(self._method_row(*triple), row, 1)
        method_grid.setColumnStretch(0,1); method_grid.setColumnStretch(1,1); method_layout.addLayout(method_grid)
        root.addWidget(method)

        footer = QFrame(); footer.setObjectName("DataPanel")
        footer_layout = QHBoxLayout(footer); footer_layout.setContentsMargins(16,10,16,10)
        summary_text = QVBoxLayout()
        asset_label = QLabel("CMIP6 assets required"); asset_label.setObjectName("TinyLabel"); bind_text(asset_label, "climate.assets_required", self.tr)
        self.asset_count = QLabel(); self.asset_count.setObjectName("QaValue")
        expected_label = QLabel("Expected outputs"); expected_label.setObjectName("TinyLabel"); bind_text(expected_label, "climate.expected_outputs", self.tr)
        self.output_count = QLabel(); self.output_count.setObjectName("QaValue")
        summary_text.addWidget(asset_label); summary_text.addWidget(self.asset_count); summary_text.addWidget(expected_label); summary_text.addWidget(self.output_count); footer_layout.addLayout(summary_text); footer_layout.addStretch()
        self.back_btn = QPushButton("← Project"); bind_text(self.back_btn, "climate.back", self.tr); self.back_btn.clicked.connect(on_back)
        self.save_btn = QPushButton("Save"); bind_text(self.save_btn, "climate.save", self.tr); self.save_btn.clicked.connect(self._save)
        self.next_btn = QPushButton("Next: CMIP6 Data →"); bind_text(self.next_btn, "climate.next", self.tr); self.next_btn.setObjectName("PrimaryButton"); self.next_btn.clicked.connect(self._next)
        footer_layout.addWidget(self.back_btn); footer_layout.addWidget(self.save_btn); footer_layout.addWidget(self.next_btn)
        root.addWidget(footer); root.addStretch(); self.load_from_state(); self.retranslate_ui()

    def _eyebrow(self, text: str, key: str) -> QLabel:
        label = QLabel(text); label.setObjectName("SectionEyebrow"); bind_text(label, key, self.tr); return label

    def _method_row(self, key_id: str, key: str, value: str) -> QFrame:
        row = QFrame(); row.setObjectName("MethodRow")
        layout = QHBoxLayout(row); layout.setContentsMargins(0,7,0,7)
        key_label = QLabel(key); key_label.setObjectName("MethodKey"); bind_text(key_label, key_id, self.tr)
        value_label = QLabel(value); value_label.setObjectName("MethodValue")
        value_key = {
            "climate.method.future": "climate.method.future.value",
            "climate.method.ensemble": "climate.method.ensemble.value",
        }.get(key_id)
        if value_key:
            bind_text(value_label, value_key, self.tr)
        layout.addWidget(key_label); layout.addStretch(); layout.addWidget(value_label); return row

    def _update_advanced_note(self, checked: bool) -> None:
        self.advanced_note.setVisible(checked)

    def _update_mode(self, *_args) -> None:
        advanced = self.advanced.isChecked()
        self.state.climate_mode = "advanced" if advanced else "reproducible"
        if not advanced:
            for key, cb in self.scenario_checks.items(): cb.setChecked(key in DEFAULT_SCENARIOS)
            for key, cb in self.period_checks.items(): cb.setChecked(key in DEFAULT_PERIODS)
            for key, cb in self.gcm_checks.items(): cb.setChecked(key in DEFAULT_GCMS)
        for cb in [*self.scenario_checks.values(), *self.period_checks.values(), *self.gcm_checks.values()]:
            cb.setEnabled(advanced)
        self._update_advanced_note(advanced)
        self._sync_state()

    def load_from_state(self) -> None:
        """Reload controls after opening a project or changing projects."""
        advanced = self.state.climate_mode == "advanced"
        # Block only the radio group side effects implicitly by setting all
        # checkboxes first; _update_mode() performs one authoritative sync.
        self.advanced.setChecked(advanced)
        self.recommended.setChecked(not advanced)
        selected_scenarios = set(self.state.scenarios if advanced else DEFAULT_SCENARIOS)
        selected_periods = set(self.state.periods if advanced else DEFAULT_PERIODS)
        selected_gcms = set(self.state.gcms if advanced else DEFAULT_GCMS)
        for key, cb in self.scenario_checks.items():
            cb.setChecked(key in selected_scenarios)
        for key, cb in self.period_checks.items():
            cb.setChecked(key in selected_periods)
        for key, cb in self.gcm_checks.items():
            cb.setChecked(key in selected_gcms)
        self._update_mode()

    def _selection_valid(self) -> bool:
        return bool(self.state.scenarios and self.state.periods and self.state.gcms)

    def _save(self) -> bool:
        self._sync_state()
        if not self._selection_valid():
            QMessageBox.warning(self, self.tr.text("climate.selection_required.title"), self.tr.text("climate.selection_required.text"))
            return False
        self.on_config_saved()
        return True

    def _next(self) -> None:
        if self._save():
            self.on_next()

    def _sync_state(self) -> None:
        self.state.climate_mode = "advanced" if self.advanced.isChecked() else "reproducible"
        self.state.scenarios = [k for k, cb in self.scenario_checks.items() if cb.isChecked()]
        self.state.periods = [k for k, cb in self.period_checks.items() if cb.isChecked()]
        self.state.gcms = [k for k, cb in self.gcm_checks.items() if cb.isChecked()]
        self.asset_count.setText(f"{dynamic_asset_total(self.state)} assets")
        self.output_count.setText(f"{expected_epw_count(self.state)} EPW")
        self.fingerprint.setText(configuration_fingerprint(self.state))
        self._refresh_summary_strip()

    def _refresh_summary_strip(self) -> None:
        scenarios = [SCENARIO_LABELS.get(x, x) for x in self.state.scenarios]
        periods = list(self.state.periods)
        gcms = list(self.state.gcms)
        expected = expected_epw_count(self.state)
        values = {
            "climate.strip.scenarios": (
                self.tr.text("climate.summary.scenarios.value", count=len(scenarios)),
                " · ".join(scenarios) or "—",
            ),
            "climate.strip.time_slices": (
                self.tr.text("climate.summary.time.value", text=" / ".join(periods) or "—"),
                "21-year centered windows" if self.tr.language == "en" else "21 年中心窗口",
            ),
            "climate.strip.ensemble": (
                self.tr.text("climate.summary.ensemble.value", count=len(gcms)),
                self.tr.text("climate.summary.ensemble.detail"),
            ),
            "climate.strip.expected": (
                self.tr.text("climate.summary.expected.value", count=expected),
                self.tr.text("climate.summary.expected.detail"),
            ),
        }
        for key, (value, detail) in values.items():
            pair = self.summary_strip_labels.get(key)
            if pair:
                pair[0].setText(value)
                pair[1].setText(detail)

    def retranslate_ui(self) -> None:
        retranslate_tree(self, self.tr)
        self._sync_state()
