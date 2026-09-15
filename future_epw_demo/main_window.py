from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .app_settings import AppSettingsStore, reopen_candidate
from .backend import WorkflowBackend
from .demo_state import WorkflowState
from .i18n import Translator, bind_text, retranslate_tree
from .pages.climate_page import ClimatePage
from .pages.cmip6_page import CMIP6Page
from .pages.generate_page import GeneratePage
from .pages.project_page import ProjectPage
from .pages.validation_page import ValidationPage
from .project_workspace import ProjectWorkspace
from .runner import WorkflowRunner
from .runtime_paths import resource_path
from .settings_dialog import SettingsDialog
from .theme import scaled_app_style
from .widgets import NavStepButton
from .workflow_state import WorkflowStateStore
from .welcome_dialog import WelcomeDialog

NAV_KEYS = ["nav.project", "nav.climate", "nav.cmip6", "nav.generate", "nav.validation"]


class MainWindow(QMainWindow):
    def __init__(self, state: WorkflowState, settings_store: AppSettingsStore | None = None):
        super().__init__()
        self.state = state
        self.workspace: ProjectWorkspace | None = None
        self.backend = WorkflowBackend()
        self.cmip6_runner = WorkflowRunner(self)
        self.generate_runner = WorkflowRunner(self)
        self.settings_store = settings_store or AppSettingsStore()
        self.settings = self.settings_store.load()
        self.tr = Translator(self.settings.language)

        self.setWindowTitle(self.tr.text("app.name"))
        self.resize(1280, 820)
        self.setMinimumSize(1180, 760)
        self.setStyleSheet(scaled_app_style(self.settings.text_scale))
        self.nav_buttons: list[NavStepButton] = []
        self.stack = QStackedWidget()
        self.current_index = 0
        self._workflow_record = None
        self._load_icon()
        self._build_shell()
        self.apply_preferences()
        reopened = self.try_reopen_last_project()
        if not reopened and not self.settings.welcome_seen:
            QTimer.singleShot(0, self._maybe_show_welcome)

    def _load_icon(self) -> None:
        icon_path = resource_path("assets", "app_icon.png")
        if icon_path.exists():
            self.app_icon_path = icon_path
            self.setWindowIcon(QIcon(str(icon_path)))
        else:
            self.app_icon_path = None

    def _build_shell(self) -> None:
        root = QFrame()
        root.setObjectName("AppSurface")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        top = QFrame()
        top.setObjectName("TopBar")
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(22, 9, 22, 9)
        top_layout.setSpacing(10)

        if self.app_icon_path:
            icon_label = QLabel()
            pixmap = QPixmap(str(self.app_icon_path)).scaled(
                28, 28, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            icon_label.setPixmap(pixmap)
            icon_label.setFixedSize(28, 28)
            top_layout.addWidget(icon_label)

        brand_col = QWidget()
        brand_col.setObjectName("BrandColumn")
        brand_layout = QVBoxLayout(brand_col)
        brand_layout.setContentsMargins(0, 0, 0, 0)
        brand_layout.setSpacing(0)
        self.app_name = QLabel(self.tr.text("app.name"))
        self.app_name.setObjectName("BrandName")
        bind_text(self.app_name, "app.name", self.tr)
        self.research_tag = QLabel(self.tr.text("app.tagline"))
        self.research_tag.setObjectName("ResearchTag")
        bind_text(self.research_tag, "app.tagline", self.tr)
        brand_layout.addWidget(self.app_name)
        brand_layout.addWidget(self.research_tag)
        top_layout.addWidget(brand_col)

        self.mode_chip = QLabel(self.tr.text("app.mode"))
        self.mode_chip.setObjectName("ModeChip")
        bind_text(self.mode_chip, "app.mode", self.tr)
        top_layout.addSpacing(12)
        top_layout.addWidget(self.mode_chip)
        top_layout.addStretch()

        self.project_label = QLabel(self.tr.text("app.project_chip", name=self.state.project_name))
        self.project_label.setObjectName("ProjectChip")
        top_layout.addWidget(self.project_label)
        self.settings_button = QPushButton("⚙")
        self.settings_button.setObjectName("SettingsButton")
        self.settings_button.setFixedSize(34, 30)
        self.settings_button.setToolTip(self.tr.text("app.settings"))
        self.settings_button.clicked.connect(self._open_settings)
        top_layout.addWidget(self.settings_button)
        root_layout.addWidget(top)

        body = QWidget()
        body.setObjectName("BodySurface")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(210)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(14, 17, 12, 12)
        side_layout.setSpacing(3)

        self.steps_label = QLabel(self.tr.text("app.workflow"))
        self.steps_label.setObjectName("SectionEyebrow")
        bind_text(self.steps_label, "app.workflow", self.tr)
        side_layout.addWidget(self.steps_label)
        side_layout.addSpacing(6)

        for i, key in enumerate(NAV_KEYS):
            btn = NavStepButton(i + 1, self.tr.text(key))
            btn.title_label.setProperty("i18nKey", key)
            btn.clicked.connect(lambda _=False, idx=i: self.set_page(idx))
            self.nav_buttons.append(btn)
            side_layout.addWidget(btn)
        side_layout.addStretch()

        self.build_label = QLabel(self.tr.text("app.version"))
        self.build_label.setObjectName("BuildLabel")
        bind_text(self.build_label, "app.version", self.tr)
        side_layout.addWidget(self.build_label)

        content_host = QWidget()
        content_host.setObjectName("ContentSurface")
        content_layout = QVBoxLayout(content_host)
        content_layout.setContentsMargins(30, 25, 30, 0)
        content_layout.setSpacing(0)
        content_layout.addWidget(self.stack)
        content_host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        workspace_provider = lambda: self.workspace
        self.project_page = ProjectPage(
            self.state,
            on_next=lambda: self.set_page(1),
            on_project_saved=self._project_saved,
            translator=self.tr,
        )
        self.climate_page = ClimatePage(
            self.state,
            on_next=lambda: self.set_page(2),
            on_back=lambda: self.set_page(0),
            on_config_saved=self._save_climate_config,
            translator=self.tr,
        )
        self.cmip6_page = CMIP6Page(
            self.state,
            self.backend,
            self.cmip6_runner,
            workspace_provider,
            on_state_change=self.refresh_status,
            translator=self.tr,
        )
        self.generate_page = GeneratePage(
            self.state,
            self.backend,
            self.generate_runner,
            workspace_provider,
            on_state_change=self.refresh_status,
            translator=self.tr,
        )
        self.validation_page = ValidationPage(self.state, workspace_provider, translator=self.tr)

        self.stack.addWidget(self._wrap_scrollable(self.project_page))
        for page in [self.climate_page, self.cmip6_page, self.generate_page, self.validation_page]:
            self.stack.addWidget(self._wrap_scrollable(page))

        body_layout.addWidget(sidebar)
        body_layout.addWidget(content_host, 1)
        root_layout.addWidget(body, 1)

        bottom = QFrame()
        bottom.setObjectName("BottomBar")
        bottom_layout = QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(22, 6, 22, 6)
        self.cache_label = QLabel()
        self.provider_label = QLabel()
        self.project_status = QLabel()
        for widget in [self.cache_label, self.provider_label, self.project_status]:
            widget.setObjectName("StatusBarText")
        bottom_layout.addWidget(self.cache_label)
        bottom_layout.addSpacing(20)
        bottom_layout.addWidget(self.provider_label)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.project_status)
        root_layout.addWidget(bottom)

        self.setCentralWidget(root)
        self.set_page(0)

    @staticmethod
    def _wrap_scrollable(page: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        return scroll

    def _project_saved(self, ws: ProjectWorkspace) -> None:
        self.workspace = ws
        self.state.project_name = ws.project_name
        self.state.project_root = str(ws.root)
        self.state.city_name = ws.display_city
        self.state.cities = [ws.display_city]
        self.state.scenarios = list(ws.scenarios)
        self.state.periods = [str(x) for x in ws.periods]
        self.state.gcms = list(ws.gcms)
        self.state.climate_mode = ws.climate_mode
        self.climate_page.load_from_state()
        self.settings = replace(self.settings, last_project_path=str(ws.root))
        self.settings_store.save(self.settings)
        self._sync_workspace_status()
        self.cmip6_page.refresh_from_workspace()
        self.generate_page.refresh_from_workspace()
        self.validation_page.refresh()
        self.refresh_status()

    def try_reopen_last_project(self) -> bool:
        root = reopen_candidate(self.settings)
        if root is None:
            return False
        ws = self.project_page.open_project_path(root, silent=True)
        if ws is None:
            return False
        snap = ws.status_snapshot()
        self.set_page(2 if (snap.cmip6_complete > 0 or snap.remote_ready > 0) else 0)
        return True

    def _maybe_show_welcome(self) -> None:
        if self.workspace is not None or self.settings.welcome_seen:
            return
        dialog = WelcomeDialog(self.tr, self)
        dialog.exec()
        self.settings = replace(self.settings, welcome_seen=True)
        self.settings_store.save(self.settings)
        if dialog.requested_action == "open":
            self.project_page._open_existing_project()

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self.tr, self)
        if dialog.exec() != SettingsDialog.DialogCode.Accepted:
            return
        self.settings = dialog.settings
        self.settings_store.save(self.settings)
        self.apply_preferences()

    def apply_preferences(self) -> None:
        self.tr.set_language(self.settings.language)
        self.setStyleSheet(scaled_app_style(self.settings.text_scale))
        self.cmip6_page.set_default_log_visibility(self.settings.show_detailed_log)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr.text("app.name"))
        retranslate_tree(self, self.tr)
        self.settings_button.setToolTip(self.tr.text("app.settings"))
        for page in [self.project_page, self.climate_page, self.cmip6_page, self.generate_page, self.validation_page]:
            if hasattr(page, "retranslate_ui"):
                page.retranslate_ui()
        self.refresh_status()

    def _save_climate_config(self) -> None:
        if self.workspace is None:
            return
        self.workspace.project_name = self.state.project_name
        self.workspace.update_climate_selection(
            mode=self.state.climate_mode,
            scenarios=list(self.state.scenarios),
            periods=list(self.state.periods),
            gcms=list(self.state.gcms),
        )
        self._sync_workspace_status()
        self.cmip6_page.refresh_from_workspace()
        self.generate_page.refresh_from_workspace()

    def _sync_workspace_status(self) -> None:
        if self.workspace is None:
            self._workflow_record = None
            return
        active = self.cmip6_runner.is_running or self.generate_runner.is_running
        self._workflow_record = WorkflowStateStore(self.workspace).reconcile(active_process=active)
        snap = self.workspace.status_snapshot()
        outcome = self.workspace.validation_outcome()
        self.state.cmip6_total = snap.cmip6_total
        self.state.cmip6_complete = snap.cmip6_complete
        self.state.city_cached = snap.city_cached
        self.state.remote_ready = snap.remote_ready
        self.state.cmip6_running = bool(
            self._workflow_record.state in {"running", "pausing"}
            and self._workflow_record.current_stage == "stage02"
        )
        self.state.cmip6_failed = 1 if (
            self._workflow_record.state == "failed" and self._workflow_record.current_stage == "stage02"
        ) else 0
        self.state.factors_ready = snap.factors_ready
        self.state.fallback_rows = snap.fallback_rows
        self.state.generation_complete = snap.epw_count
        self.state.validation_passed = True if outcome in {"pass", "warning"} else (False if outcome == "fail" else None)
        self.state.audit_groups = snap.audit_groups

    def _nav_state(self, index: int) -> tuple[str, str]:
        if index == 0:
            return ("status.complete", "complete") if self.workspace is not None else (("status.active", "active") if index == self.current_index else ("status.pending", "pending"))
        if index == 1:
            if self.workspace is not None and self.workspace.project_protocol() == "R1":
                return "status.complete", "complete"
        if index == 2:
            if self.cmip6_runner.is_running:
                return "status.running", "running"
            if self._workflow_record is not None and self._workflow_record.state == "failed" and self._workflow_record.current_stage == "stage02":
                return "status.failed", "warning"
            if self.state.cmip6_total > 0 and self.state.cmip6_complete >= self.state.cmip6_total:
                return "status.complete", "complete"
            if self.state.cmip6_complete > 0 or self.state.remote_ready > 0:
                return "status.paused", "pending"
        if index == 3:
            if self.generate_runner.is_running:
                return "status.running", "running"
            if self._workflow_record is not None and self._workflow_record.current_stage in {"stage03", "stage04", "stage05"} and self._workflow_record.state == "failed":
                return "status.failed", "warning"
            if self.workspace is not None and self.workspace.generation_complete():
                return "status.complete", "complete"
        if index == 4 and self.workspace is not None:
            outcome = self.workspace.validation_outcome()
            if outcome == "warning":
                return "status.warning", "warning"
            if outcome == "pass":
                return "status.complete", "complete"
            if outcome == "fail":
                return "status.failed", "warning"
        if index == self.current_index:
            return "status.active", "active"
        return "status.pending", "pending"

    def _refresh_nav(self) -> None:
        for i, button in enumerate(self.nav_buttons):
            status_key, kind = self._nav_state(i)
            button.set_step_state(self.tr.text(status_key), active=i == self.current_index, kind=kind)
            button.title_label.setText(self.tr.text(NAV_KEYS[i]))

    def set_page(self, index: int) -> None:
        self.current_index = max(0, min(index, self.stack.count() - 1))
        self.stack.setCurrentIndex(self.current_index)
        self._sync_workspace_status()
        if self.current_index == 2:
            self.cmip6_page.refresh_from_workspace()
        elif self.current_index == 3:
            self.generate_page.refresh_from_workspace()
        elif self.current_index == 4:
            self.validation_page.refresh()
        self._refresh_nav()
        self.refresh_status()

    def refresh_status(self) -> None:
        if not hasattr(self, "cache_label"):
            return
        self._sync_workspace_status()
        project_name = self.workspace.project_name if self.workspace else self.state.project_name
        self.project_label.setText(self.tr.text("app.project_chip", name=project_name))
        self.cache_label.setText(self.tr.text("app.cache", complete=self.state.cmip6_complete, total=self.state.cmip6_total))
        self.provider_label.setText(self.tr.text("app.provider", provider=self.state.active_provider))
        if self.cmip6_runner.is_running:
            status = self.cmip6_runner.current_step_name
        elif self.generate_runner.is_running:
            status = self.generate_runner.current_step_name
        elif self.state.validation_passed is True:
            status = self.tr.text("status.pass_warnings" if self.state.fallback_rows > 0 else "status.pass")
        elif self.state.validation_passed is False:
            status = self.tr.text("status.fail")
        elif self.workspace is None:
            status = self.tr.text("status.project_not_saved")
        else:
            status = self.tr.text("status.ready")
        self.project_status.setText(self.tr.text("app.status", status=status))
        self._refresh_nav()
