from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path


ENGINE_STAGE_ALLOWLIST = {
    "00_check_environment.py",
    "01_prepare_manifest.py",
    "02_extract_cmip6.py",
    "03_build_climate_factors.py",
    "04_generate_future_epw.py",
    "05_validate_outputs.py",
}


def run_engine_stage(argv: list[str]) -> int:
    from future_epw_demo.runtime_paths import resource_path

    if not argv:
        print("Missing engine stage name", file=sys.stderr)
        return 2
    stage = Path(argv[0]).name
    if stage not in ENGINE_STAGE_ALLOWLIST:
        print(f"Unsupported engine stage: {stage}", file=sys.stderr)
        return 2
    engine_dir = resource_path("engine_core")
    script = engine_dir / stage
    if not script.is_file():
        print(f"Bundled engine stage is missing: {script}", file=sys.stderr)
        return 2

    old_argv = sys.argv[:]
    old_cwd = Path.cwd()
    inserted = False
    try:
        sys.argv = [str(script), *argv[1:]]
        engine_text = str(engine_dir)
        if engine_text not in sys.path:
            sys.path.insert(0, engine_text)
            inserted = True
        os.chdir(engine_dir)
        try:
            runpy.run_path(str(script), run_name="__main__")
        except SystemExit as exc:
            code = exc.code
            if code is None:
                return 0
            return int(code) if isinstance(code, int) else 1
        return 0
    finally:
        os.chdir(old_cwd)
        sys.argv = old_argv
        if inserted:
            try:
                sys.path.remove(str(engine_dir))
            except ValueError:
                pass


def run_self_test() -> int:
    from future_epw_demo.app_settings import AppSettings
    from future_epw_demo.backend import WorkflowBackend
    from future_epw_demo.demo_state import WorkflowState, configuration_fingerprint, dynamic_asset_total, expected_epw_count
    from future_epw_demo.eta import ExtractionETA
    from future_epw_demo.i18n import Translator
    from future_epw_demo.preflight import PreflightCheck, PreflightReport
    from future_epw_demo.weather_library import WeatherCatalog
    from future_epw_demo.workflow_state import WorkflowStateRecord

    from future_epw_demo.runtime_paths import resource_path
    assert resource_path("VERSION").read_text(encoding="utf-8").strip() == "1.0.0"
    assert AppSettings().language == "en"
    assert Translator("zh_CN").text("nav.project") == "项目"
    assert ExtractionETA().estimate(10).ready is False
    state = WorkflowState()
    assert expected_epw_count(state) == 36
    assert configuration_fingerprint(state).endswith("-5GCM")
    assert WorkflowStateRecord().cmip6_total == 200
    advanced = WorkflowState(climate_mode="advanced", scenarios=["ssp126"], periods=["2040"], gcms=["ACCESS-CM2"], cities=["Tokyo"])
    assert dynamic_asset_total(advanced) == 20
    assert expected_epw_count(advanced) == 2
    assert len(WeatherCatalog().records) >= 40
    assert PreflightReport((PreflightCheck("self-test", True, "ok"),)).passed is True
    backend = WorkflowBackend()
    for name in [
        "00_check_environment.py",
        "01_prepare_manifest.py",
        "02_extract_cmip6.py",
        "03_build_climate_factors.py",
        "04_generate_future_epw.py",
        "05_validate_outputs.py",
    ]:
        assert (backend.engine_dir / name).exists(), name
    assert (backend.engine_dir / "inputs" / "catalog" / "catalog_subset_205_assets.csv").exists()
    print("Future EPW Generator functional self-test: PASS")
    return 0


def run_gui() -> int:
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from future_epw_demo.demo_state import WorkflowState
    from future_epw_demo.main_window import MainWindow

    app = QApplication(sys.argv)
    from future_epw_demo.runtime_paths import resource_path
    icon_path = resource_path("assets", "app_icon.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    window = MainWindow(WorkflowState())
    window.show()
    return app.exec()


if __name__ == "__main__":
    if "--engine-stage" in sys.argv:
        idx = sys.argv.index("--engine-stage")
        raise SystemExit(run_engine_stage(sys.argv[idx + 1:]))
    if "--self-test" in sys.argv:
        raise SystemExit(run_self_test())
    raise SystemExit(run_gui())
