from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from .project_workspace import ProjectWorkspace
from .runtime_paths import frozen_engine_executable, is_frozen, resource_path


@dataclass(frozen=True)
class BackendPaths:
    engine_dir: Path
    python_executable: str


@dataclass(frozen=True)
class WorkflowCommands:
    stage00: list[str]
    stage01: list[str]
    stage02: list[str]
    stage02_status: list[str]
    stage03: list[str]
    stage04: list[str]
    stage05: list[str]


class WorkflowBackend:
    def __init__(self, engine_dir: Path | str | None = None, python_executable: str | None = None, frozen_mode: bool | None = None):
        self.engine_dir = Path(engine_dir) if engine_dir else resource_path("engine_core")
        self.frozen_mode = is_frozen() if frozen_mode is None else bool(frozen_mode)
        if python_executable is not None:
            self.python_executable = python_executable
        elif self.frozen_mode:
            self.python_executable = str(frozen_engine_executable())
        else:
            self.python_executable = sys.executable

    def _script(self, name: str) -> str:
        path = self.engine_dir / name
        if not path.exists():
            raise FileNotFoundError(f"Bundled workflow script missing: {path}")
        return str(path)


    def _stage_command(self, name: str, *args: str) -> list[str]:
        script = self._script(name)
        if self.frozen_mode:
            return [self.python_executable, "--engine-stage", name, *args]
        return [self.python_executable, script, *args]

    def commands(self, ws: ProjectWorkspace) -> WorkflowCommands:
        city = ws.city
        catalog = self.engine_dir / "inputs" / "catalog" / "catalog_subset_205_assets.csv"
        stage00 = [
            *self._stage_command("00_check_environment.py"),
            "--epw-dir", str(ws.baseline_dir),
            "--cities", city,
            "--location-spec", str(ws.location_spec_file),
            "--out", str(ws.outputs_dir / "environment_report.json"),
        ]
        stage01 = [
            *self._stage_command("01_prepare_manifest.py"),
            "--catalog", str(catalog),
            "--out-dir", str(ws.manifest_dir),
            "--models", *ws.effective_gcms(),
            "--experiments", "historical", *ws.effective_scenarios(),
            "--periods", *ws.effective_periods(),
        ]
        stage02 = [
            *self._stage_command("02_extract_cmip6.py"),
            "--manifest", str(ws.manifest_file),
            "--epw-dir", str(ws.baseline_dir),
            "--cities", city,
            "--location-spec", str(ws.location_spec_file),
            "--cache-dir", str(ws.cache_dir),
            "--city-cache-dir", str(ws.city_cache_dir),
            "--legacy-cache-dir", str(ws.legacy_cache_dir),
            "--legacy-city-cache-dir", str(ws.legacy_city_cache_dir),
            "--stop-file", str(ws.stop_file),
        ]
        stage02_status = [
            *self._stage_command("02_extract_cmip6.py"),
            "--manifest", str(ws.manifest_file),
            "--epw-dir", str(ws.baseline_dir),
            "--cities", city,
            "--location-spec", str(ws.location_spec_file),
            "--cache-dir", str(ws.cache_dir),
            "--city-cache-dir", str(ws.city_cache_dir),
            "--legacy-cache-dir", str(ws.legacy_cache_dir),
            "--legacy-city-cache-dir", str(ws.legacy_city_cache_dir),
            "--status",
            "--status-out", str(ws.cmip6_status_file),
        ]
        stage03 = [
            *self._stage_command("03_build_climate_factors.py"),
            "--manifest", str(ws.manifest_file),
            "--cache-dir", str(ws.cache_dir),
            "--cities", city,
            "--out-dir", str(ws.factors_dir),
            "--models", *ws.effective_gcms(),
            "--scenarios", *ws.effective_scenarios(),
            "--labels", *ws.effective_periods(),
        ]
        selectors = list(ws.effective_gcms()) + ["mean"]
        stage04 = [
            *self._stage_command("04_generate_future_epw.py"),
            "--per-gcm", str(ws.factors_dir / "climate_factors_per_gcm.csv"),
            "--ensemble", str(ws.factors_dir / "climate_factors_ensemble.csv"),
            "--epw-dir", str(ws.baseline_dir),
            "--location-spec", str(ws.location_spec_file),
            "--out-dir", str(ws.epw_dir),
            "--audit-dir", str(ws.audit_dir),
            "--cities", city,
            "--scenarios", *ws.effective_scenarios(),
            "--labels", *ws.effective_periods(),
            "--selectors", *selectors,
        ]
        stage05 = [
            *self._stage_command("05_validate_outputs.py"),
            "--epw-dir", str(ws.epw_dir),
            "--audit-dir", str(ws.audit_dir),
            "--out-dir", str(ws.validation_dir),
        ]
        return WorkflowCommands(stage00, stage01, stage02, stage02_status, stage03, stage04, stage05)

    def clear_pause_request(self, ws: ProjectWorkspace) -> None:
        ws.stop_file.unlink(missing_ok=True)

    def request_pause(self, ws: ProjectWorkspace) -> None:
        ws.runtime_dir.mkdir(parents=True, exist_ok=True)
        ws.stop_file.write_text("pause requested\n", encoding="utf-8")
