from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QMessageBox, QPushButton, QRadioButton, QVBoxLayout, QWidget,
)

from ..demo_state import WorkflowState
from ..epw_meta import EPWMetadata, parse_epw_metadata
from ..errors import WorkflowUserError
from ..i18n import Translator, bind_text, retranslate_tree
from ..project_workspace import ProjectWorkspace, SUPPORTED_WMO_TO_CITY
from ..widgets import card, metadata_block, metric_cell, page_header
from ..weather_library import WeatherCatalog, WeatherLibrary, WeatherRecord


class ProjectPage(QWidget):
    """Project setup page backed by a real CLI-compatible workspace."""

    def __init__(
        self,
        state: WorkflowState,
        on_next: Callable[[], None],
        on_project_saved: Callable[[ProjectWorkspace], None],
        translator: Translator | None = None,
    ):
        super().__init__()
        self.state = state
        self.on_next = on_next
        self.on_project_saved = on_project_saved
        self.tr = translator or Translator()
        self.selected_epw: Path | None = Path(state.baseline_source) if state.baseline_source else None
        self.current_meta: EPWMetadata | None = None
        self.active_workspace: ProjectWorkspace | None = None
        self.baseline_origin: dict | None = None
        self.weather_catalog = WeatherCatalog()
        self.weather_library = WeatherLibrary()
        self._library_records: list[WeatherRecord] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(13)

        title, subtitle = page_header(
            "Project Setup",
            "Define the baseline weather source, spatial reference and reproducible project workspace",
            translator=self.tr,
            title_key="project.title",
            subtitle_key="project.subtitle",
        )
        root.addWidget(title)
        root.addWidget(subtitle)

        top_row = QHBoxLayout()
        top_row.setSpacing(13)

        info_card, info_layout = card("Project", translator=self.tr, title_key="project.card.project")
        info_grid = QGridLayout()
        info_grid.setHorizontalSpacing(10)
        info_grid.setVerticalSpacing(10)
        self.project_name = QLineEdit(state.project_name)
        self.project_folder = QLineEdit(state.project_root or r"C:\FutureEPW\Singapore_Future_EPW")
        self.folder_btn = QPushButton("Browse…")
        bind_text(self.folder_btn, "common.browse", self.tr)
        self.folder_btn.clicked.connect(self._browse_folder)
        info_grid.addWidget(self._field_label("Project name", "project.name"), 0, 0)
        info_grid.addWidget(self.project_name, 0, 1, 1, 2)
        info_grid.addWidget(self._field_label("Project folder", "project.folder"), 1, 0)
        info_grid.addWidget(self.project_folder, 1, 1)
        info_grid.addWidget(self.folder_btn, 1, 2)
        info_grid.setColumnStretch(1, 1)
        info_layout.addLayout(info_grid)
        top_row.addWidget(info_card, 5)

        location_card, location_layout = card("Location", translator=self.tr, title_key="project.location")
        loc_grid = QGridLayout()
        loc_grid.setHorizontalSpacing(9)
        loc_grid.setVerticalSpacing(10)
        self.city = QLineEdit(state.city_name)
        self.station = QLineEdit(state.station_name)
        self.station.setReadOnly(True)
        self.latitude = QLineEdit(f"{state.latitude:.5f}")
        self.longitude = QLineEdit(f"{state.longitude:.5f}")
        loc_grid.addWidget(self._field_label("City", "project.city"), 0, 0)
        loc_grid.addWidget(self.city, 0, 1, 1, 3)
        loc_grid.addWidget(self._field_label("Station", "project.station"), 1, 0)
        loc_grid.addWidget(self.station, 1, 1, 1, 3)
        loc_grid.addWidget(self._field_label("Latitude", "project.latitude"), 2, 0)
        loc_grid.addWidget(self.latitude, 2, 1)
        loc_grid.addWidget(self._field_label("Longitude", "project.longitude"), 2, 2)
        loc_grid.addWidget(self.longitude, 2, 3)
        loc_grid.setColumnStretch(1, 1)
        loc_grid.setColumnStretch(3, 1)
        location_layout.addLayout(loc_grid)
        self.use_epw_coords = QCheckBox("Use coordinates from EPW")
        bind_text(self.use_epw_coords, "project.use_epw_coords", self.tr)
        self.use_epw_coords.setChecked(True)
        self.use_epw_coords.toggled.connect(self._toggle_coordinate_source)
        location_layout.addWidget(self.use_epw_coords)
        self.latitude.setDisabled(True)
        self.longitude.setDisabled(True)
        top_row.addWidget(location_card, 3)
        root.addLayout(top_row)

        weather, weather_layout = card("Baseline Weather", translator=self.tr, title_key="project.baseline_weather")
        source_row = QHBoxLayout()
        self.library_mode = QRadioButton("Weather Library")
        bind_text(self.library_mode, "project.weather_library", self.tr)
        self.local_mode = QRadioButton("Local EPW")
        bind_text(self.local_mode, "project.local_epw", self.tr)
        source_group = QButtonGroup(self); source_group.addButton(self.library_mode); source_group.addButton(self.local_mode)
        self.library_mode.setChecked(not bool(self.selected_epw))
        self.local_mode.setChecked(bool(self.selected_epw))
        self.library_mode.toggled.connect(self._update_weather_source_mode)
        self.local_mode.toggled.connect(self._update_weather_source_mode)
        source_row.addWidget(self.library_mode); source_row.addWidget(self.local_mode); source_row.addStretch()
        weather_layout.addLayout(source_row)

        self.library_panel = QFrame()
        self.library_panel.setObjectName("WeatherLibraryPanel")
        library_layout = QVBoxLayout(self.library_panel)
        library_layout.setContentsMargins(0, 4, 0, 6)
        library_layout.setSpacing(7)

        search_row = QHBoxLayout()
        search_label = self._field_label("Search city", "project.weather_library.search_label")
        self.library_search = QLineEdit()
        self.library_search.setPlaceholderText(self.tr.text("project.weather_library.search"))
        search_row.addWidget(search_label)
        search_row.addWidget(self.library_search, 1)
        library_layout.addLayout(search_row)

        results_label = self._field_label("Search results", "project.weather_library.results")
        library_layout.addWidget(results_label)
        self.library_results = QListWidget()
        self.library_results.setObjectName("WeatherLibraryResults")
        self.library_results.setMinimumHeight(74)
        self.library_results.setMaximumHeight(118)
        library_layout.addWidget(self.library_results)

        result_actions = QHBoxLayout()
        self.library_detail = QLabel()
        self.library_detail.setObjectName("Muted")
        self.library_detail.setWordWrap(True)
        self.library_use_btn = QPushButton(self.tr.text("project.weather_library.download_use"))
        self.library_use_btn.clicked.connect(self._use_library_record)
        result_actions.addWidget(self.library_detail, 1)
        result_actions.addWidget(self.library_use_btn)
        library_layout.addLayout(result_actions)
        weather_layout.addWidget(self.library_panel)

        self.library_search.textChanged.connect(self._filter_weather_library)
        self.library_results.currentRowChanged.connect(self._library_selection_changed)
        self._filter_weather_library("")

        file_row = QGridLayout()
        file_row.setHorizontalSpacing(10)
        self.epw_path = QLineEdit(Path(state.baseline_source).name if state.baseline_source else self.tr.text("project.select_epw"))
        self.epw_path.setReadOnly(True)
        self.epw_btn = QPushButton("Browse…")
        bind_text(self.epw_btn, "common.browse", self.tr)
        self.epw_btn.clicked.connect(self._browse_epw)
        file_row.addWidget(self._field_label("Baseline EPW", "project.baseline_epw"), 0, 0)
        file_row.addWidget(self.epw_path, 0, 1)
        file_row.addWidget(self.epw_btn, 0, 2)
        file_row.setColumnStretch(1, 1)
        weather_layout.addLayout(file_row)
        self._update_weather_source_mode()

        metadata_panel = QFrame()
        metadata_panel.setObjectName("WeatherMetadataPanel")
        metadata_grid = QGridLayout(metadata_panel)
        metadata_grid.setContentsMargins(0, 0, 0, 0)
        metadata_grid.setHorizontalSpacing(0)
        metadata_grid.setVerticalSpacing(0)
        self.meta_values: dict[str, QLabel] = {}
        meta_specs = [
            ("Station", "project.meta.station", state.station_name),
            ("WMO", "project.meta.wmo", state.wmo),
            ("Elevation", "project.meta.elevation", f"{state.elevation:g} m"),
            ("Hours", "project.meta.hours", str(state.baseline_hours)),
            ("Latitude", "project.meta.latitude", f"{state.latitude:.5f}°"),
            ("Longitude", "project.meta.longitude", f"{state.longitude:.5f}°"),
            ("Source", "project.meta.source", "OneBuilding TMYx"),
            ("Status", "project.meta.status", self.tr.text("project.epw.status.waiting")),
        ]
        for i, (label, label_key, value) in enumerate(meta_specs):
            row, col = divmod(i, 4)
            object_name = "Success" if label == "Status" and state.baseline_source else "MetaValue"
            block = metadata_block(label, value, object_name)
            block.setObjectName("WeatherMetric")
            labels = block.findChildren(QLabel)
            if labels:
                bind_text(labels[0], label_key, self.tr)
                self.meta_values[label] = labels[-1]
            metadata_grid.addWidget(block, row, col)
        for col in range(4):
            metadata_grid.setColumnStretch(col, 1)
        weather_layout.addWidget(metadata_panel)
        root.addWidget(weather)

        summary = QFrame()
        summary.setObjectName("ProjectSummary")
        summary_layout = QVBoxLayout(summary)
        summary_layout.setContentsMargins(15, 12, 15, 12)
        summary_layout.setSpacing(8)
        summary_title = QLabel("Project Summary")
        summary_title.setObjectName("SectionTitle")
        bind_text(summary_title, "project.summary", self.tr)
        summary_layout.addWidget(summary_title)
        metrics = QHBoxLayout()
        metrics.setSpacing(0)
        self.summary_city = metric_cell("Cities", "1", state.city_name)
        self.summary_baseline = metric_cell("Baseline", "1 EPW", "Validated station required")
        self.summary_coords = metric_cell("Coordinates", "EPW", "Locked to weather station")
        self.summary_state = metric_cell("Project state", "Setup", "Select baseline EPW and save")
        self._bind_metric(self.summary_city, "project.summary.cities")
        self._bind_metric(self.summary_baseline, "project.summary.baseline", "project.summary.validated_station")
        self._bind_metric(self.summary_coords, "project.summary.coordinates", "project.summary.locked_station")
        self._bind_metric(self.summary_state, "project.summary.state", "project.summary.select_save", value_key="project.summary.setup")
        for widget in [self.summary_city, self.summary_baseline, self.summary_coords, self.summary_state]:
            metrics.addWidget(widget, 1)
        summary_layout.addLayout(metrics)
        root.addWidget(summary)

        note = QFrame()
        note.setObjectName("ScientificNote")
        note_layout = QHBoxLayout(note)
        note_layout.setContentsMargins(13, 9, 13, 9)
        note_layout.setSpacing(10)
        note_label = QLabel("Scientific workflow note")
        note_label.setObjectName("ScientificNoteTitle")
        bind_text(note_label, "project.note.title", self.tr)
        note_text = QLabel("Any valid 8760-hour baseline EPW can define a target location while preserving the validated R1 Stage 00–05 CMIP6 workflow.")
        note_text.setObjectName("ScientificNoteText")
        bind_text(note_text, "project.note.text", self.tr)
        note_text.setWordWrap(True)
        note_layout.addWidget(note_label)
        note_layout.addWidget(note_text, 1)
        root.addWidget(note)
        root.addStretch(1)

        action_bar = QFrame()
        action_bar.setObjectName("ActionBar")
        actions = QHBoxLayout(action_bar)
        actions.setContentsMargins(0, 10, 0, 0)
        self.helper = QLabel(self.tr.text("project.helper"))
        self.helper.setObjectName("Muted")
        self.helper.setStyleSheet("font-size: 11px;")
        actions.addWidget(self.helper)
        actions.addStretch()
        self.open_existing_btn = QPushButton("Open Existing Project…")
        bind_text(self.open_existing_btn, "project.open_existing", self.tr)
        self.open_existing_btn.clicked.connect(self._open_existing_project)
        self.save_btn = QPushButton("Save Project")
        bind_text(self.save_btn, "project.save_project", self.tr)
        self.save_btn.clicked.connect(self._save_project)
        self.next_btn = QPushButton("Next: Climate  →")
        bind_text(self.next_btn, "project.next_climate", self.tr)
        self.next_btn.setObjectName("PrimaryButton")
        self.next_btn.clicked.connect(self._next)
        actions.addWidget(self.open_existing_btn)
        actions.addWidget(self.save_btn)
        actions.addWidget(self.next_btn)
        root.addWidget(action_bar)

        if self.selected_epw and self.selected_epw.exists():
            self._load_epw(self.selected_epw)
        self.retranslate_ui()

    def _field_label(self, text: str, key: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("FieldLabel")
        bind_text(label, key, self.tr)
        return label

    def _bind_metric(self, frame: QFrame, kicker_key: str, detail_key: str | None = None, *, value_key: str | None = None) -> None:
        labels = frame.findChildren(QLabel)
        if labels:
            bind_text(labels[0], kicker_key, self.tr)
        if value_key and len(labels) > 1:
            bind_text(labels[1], value_key, self.tr)
        if detail_key and len(labels) > 2:
            bind_text(labels[2], detail_key, self.tr)

    def _toggle_coordinate_source(self, use_epw: bool) -> None:
        self.latitude.setDisabled(use_epw)
        self.longitude.setDisabled(use_epw)
        if use_epw and self.current_meta is not None:
            self.latitude.setText(f"{self.current_meta.latitude:.5f}")
            self.longitude.setText(f"{self.current_meta.longitude:.5f}")

    def _update_weather_source_mode(self, *_args) -> None:
        library_active = self.library_mode.isChecked()
        if hasattr(self, "library_panel"):
            self.library_panel.setVisible(library_active)
        if hasattr(self, "epw_btn"):
            self.epw_btn.setEnabled(not library_active)

    def _filter_weather_library(self, query: str = "") -> None:
        self._library_records = self.weather_catalog.search(query)[:8]
        self.library_results.clear()
        for record in self._library_records:
            self.library_results.addItem(
                f"{record.city}, {record.country}  —  {record.station}  ·  WMO {record.wmo}"
            )
        if self._library_records:
            self.library_results.setCurrentRow(0)
        else:
            self._library_selection_changed()

    def _selected_library_record(self) -> WeatherRecord | None:
        row = self.library_results.currentRow()
        if 0 <= row < len(self._library_records):
            return self._library_records[row]
        return None

    def _library_selection_changed(self, *_args) -> None:
        record = self._selected_library_record()
        if record is None:
            self.library_detail.setText(self.tr.text("project.weather_library.no_match"))
            self.library_use_btn.setEnabled(False)
            return
        self.library_use_btn.setEnabled(True)
        cached = self.weather_library.cached_epw(record)
        self.library_use_btn.setText(self.tr.text("project.weather_library.use_cached" if cached else "project.weather_library.download_use"))
        self.library_detail.setText(self.tr.text(
            "project.weather_library.detail", city=record.city, station=record.station, wmo=record.wmo,
            period=record.period, source=record.source, status=self.tr.text("project.weather_library.cached" if cached else "project.weather_library.not_downloaded")
        ))

    def _use_library_record(self) -> None:
        record = self._selected_library_record()
        if record is None:
            QMessageBox.warning(self, self.tr.text("project.weather_library"), self.tr.text("project.weather_library.no_match"))
            return
        self.library_mode.setChecked(True)
        self.library_use_btn.setEnabled(False)
        self.library_use_btn.setText(self.tr.text("project.weather_library.downloading"))
        try:
            epw = self.weather_library.download_and_validate(record)
            self.baseline_origin = {
                "type": "weather_library",
                "catalog_id": record.id,
                "city": record.city,
                "station": record.station,
                "wmo": record.wmo,
                "dataset": record.dataset,
                "period": record.period,
                "source": record.source,
                "download_url": record.download_url,
            }
            self._load_epw(epw, city_override=record.city)
            self.project_name.setText(f"{record.city.replace(' ', '_')}_Future_EPW")
            if not self.active_workspace:
                self.project_folder.setText(str(Path.home() / "FutureEPW" / f"{record.city.replace(' ', '_')}_Future_EPW"))
            self.helper.setText(self.tr.text("project.weather_library.ready", city=record.city, station=record.station))
        except WorkflowUserError as exc:
            QMessageBox.critical(self, self.tr.text("project.weather_library.download_failed"), exc.user_text(self.tr))
        except Exception as exc:
            QMessageBox.critical(self, self.tr.text("project.weather_library.download_failed"), str(exc))
        finally:
            self._library_selection_changed()

    def _browse_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, self.tr.text("project.select_folder_dialog"))
        if selected:
            self.project_folder.setText(selected)

    def _browse_epw(self) -> None:
        self.local_mode.setChecked(True)
        selected, _ = QFileDialog.getOpenFileName(self, self.tr.text("project.select_epw_dialog"), "", "EPW files (*.epw)")
        if selected:
            try:
                self.baseline_origin = {"type": "local"}
                self._load_epw(Path(selected))
            except Exception as exc:
                QMessageBox.critical(self, self.tr.text("project.invalid_epw"), str(exc))

    def _load_epw(self, path: Path, *, city_override: str | None = None) -> None:
        meta = parse_epw_metadata(path)
        if not meta.valid:
            raise ValueError(f"EPW must contain exactly 8760 hourly rows; found {meta.hours}.")
        catalog_match = self.weather_catalog.by_wmo(meta.wmo)
        city = (
            (city_override or "").strip()
            or (catalog_match.city if catalog_match is not None else "")
            or SUPPORTED_WMO_TO_CITY.get(meta.wmo)
            or meta.station.strip()
            or "Target City"
        )
        self.selected_epw = path
        self.current_meta = meta
        self.epw_path.setText(str(path))
        self.city.setText(city)
        self.station.setText(meta.station)
        self.state.city_name = city
        labels = self.summary_city.findChildren(QLabel)
        if len(labels) >= 3: labels[2].setText(city)
        self.use_epw_coords.setChecked(True)
        self.latitude.setText(f"{meta.latitude:.5f}")
        self.longitude.setText(f"{meta.longitude:.5f}")
        values = {
            "Station": meta.station,
            "WMO": meta.wmo,
            "Elevation": f"{meta.elevation:g} m",
            "Hours": str(meta.hours),
            "Latitude": f"{meta.latitude:.5f}°",
            "Longitude": f"{meta.longitude:.5f}°",
            "Source": meta.source or "EPW",
            "Status": self.tr.text("project.epw.status.valid"),
        }
        for key, value in values.items():
            label = self.meta_values.get(key)
            if label:
                label.setText(value)
                if key == "Status":
                    label.setObjectName("Success")
                    label.style().unpolish(label)
                    label.style().polish(label)
        self.helper.setText(self.tr.text("project.helper.valid", station=meta.station, wmo=meta.wmo))

    def _save_project(self) -> ProjectWorkspace | None:
        if not self.selected_epw or not self.selected_epw.exists():
            QMessageBox.warning(self, self.tr.text("project.dialog.baseline_required.title"), self.tr.text("project.dialog.baseline_required.text"))
            return None
        root_text = self.project_folder.text().strip()
        if not root_text:
            QMessageBox.warning(self, self.tr.text("project.dialog.folder_required.title"), self.tr.text("project.dialog.folder_required.text"))
            return None
        try:
            ws = ProjectWorkspace.create(
                root=Path(root_text),
                project_name=self.project_name.text().strip() or "Future_EPW_Project",
                city_name=self.city.text().strip(),
                baseline_source=self.selected_epw,
                latitude=float(self.latitude.text().strip()),
                longitude=float(self.longitude.text().strip()),
                use_epw_coordinates=self.use_epw_coords.isChecked(),
                scenarios=self.state.scenarios,
                periods=self.state.periods,
                gcms=self.state.gcms,
                climate_mode=self.state.climate_mode,
                baseline_origin=self.baseline_origin,
            )
        except WorkflowUserError as exc:
            QMessageBox.critical(self, self.tr.text("project.dialog.creation_failed"), exc.user_text(self.tr))
            return None
        except Exception as exc:
            QMessageBox.critical(self, self.tr.text("project.dialog.creation_failed"), str(exc))
            return None

        self._apply_workspace(ws)
        self.helper.setText(self.tr.text("project.helper.saved", path=ws.project_file))
        QMessageBox.information(self, self.tr.text("project.dialog.saved.title"), self.tr.text("project.dialog.saved.text", root=ws.root))
        return ws

    def _apply_workspace(self, ws: ProjectWorkspace) -> None:
        self.active_workspace = ws
        display_city = ws.display_city
        self.state.project_name = ws.project_name
        self.state.project_root = str(ws.root)
        self.state.baseline_source = str(ws.baseline_path)
        self.state.city_name = display_city
        self.state.cities = [display_city]
        self.state.station_name = ws.metadata.station
        self.state.wmo = ws.metadata.wmo
        self.state.latitude = ws.latitude
        self.state.longitude = ws.longitude
        self.state.elevation = ws.metadata.elevation
        self.state.baseline_hours = ws.metadata.hours
        self.state.scenarios = list(ws.scenarios)
        self.state.periods = [str(x) for x in ws.periods]
        self.state.gcms = list(ws.gcms)
        self.state.climate_mode = ws.climate_mode
        self.project_name.setText(ws.project_name)
        self.project_folder.setText(str(ws.root))
        self.city.setText(display_city)
        self.station.setText(ws.metadata.station)
        labels = self.summary_city.findChildren(QLabel)
        if len(labels) >= 3: labels[2].setText(display_city)
        self.selected_epw = ws.baseline_path
        self.current_meta = ws.metadata
        self.baseline_origin = dict(ws.baseline_origin) if ws.baseline_origin else None
        from_library = bool(self.baseline_origin and self.baseline_origin.get("type") == "weather_library")
        self.library_mode.setChecked(from_library)
        self.local_mode.setChecked(not from_library)
        self._update_weather_source_mode()
        self.epw_path.setText(str(ws.baseline_path))
        self.use_epw_coords.setChecked(ws.coordinate_source == "epw")
        self.latitude.setText(f"{ws.latitude:.5f}")
        self.longitude.setText(f"{ws.longitude:.5f}")
        self.on_project_saved(ws)

    def open_project_path(self, path: Path | str, *, silent: bool = False) -> ProjectWorkspace | None:
        try:
            ws = ProjectWorkspace.load(path)
        except WorkflowUserError as exc:
            if not silent:
                QMessageBox.critical(self, self.tr.text("project.dialog.invalid_project"), exc.user_text(self.tr))
            return None
        except Exception as exc:
            if not silent:
                QMessageBox.critical(self, self.tr.text("project.dialog.invalid_project"), str(exc))
            return None
        self._apply_workspace(ws)
        if not ws.verify_baseline_fingerprint() and not silent:
            QMessageBox.warning(self, self.tr.text("project.dialog.baseline_changed.title"), self.tr.text("project.dialog.baseline_changed.text"))
        self.helper.setText(self.tr.text("project.helper.opened", path=ws.project_file))
        return ws

    def _open_existing_project(self) -> ProjectWorkspace | None:
        selected = QFileDialog.getExistingDirectory(self, self.tr.text("project.open_project_dialog"))
        if not selected:
            return None
        return self.open_project_path(selected, silent=False)

    def _next(self) -> None:
        root_text = self.project_folder.text().strip()
        if self.active_workspace is not None and root_text:
            try:
                if Path(root_text).expanduser().resolve() == self.active_workspace.root:
                    self.on_next()
                    return
            except OSError:
                pass
        ws = self._save_project()
        if ws is not None:
            self.on_next()

    def retranslate_ui(self) -> None:
        retranslate_tree(self, self.tr)
        if hasattr(self, "library_search"):
            self.library_search.setPlaceholderText(self.tr.text("project.weather_library.search"))
            self._filter_weather_library(self.library_search.text())
        if not self.selected_epw:
            self.epw_path.setText(self.tr.text("project.select_epw"))
        if self.current_meta is not None:
            status = self.meta_values.get("Status")
            if status:
                status.setText(self.tr.text("project.epw.status.valid"))
            if self.active_workspace is not None:
                self.helper.setText(self.tr.text("project.helper.opened", path=self.active_workspace.project_file))
            else:
                self.helper.setText(self.tr.text("project.helper.valid", station=self.current_meta.station, wmo=self.current_meta.wmo))
        elif self.active_workspace is None:
            self.helper.setText(self.tr.text("project.helper"))
