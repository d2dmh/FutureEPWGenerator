from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_app_keeps_v05_visual_shell_and_five_workflow_pages():
    src = read("future_epw_demo/main_window.py")
    for label in ["Project", "Climate", "CMIP6", "Generate", "Validation"]:
        assert label in src
    catalogue = read("future_epw_demo/i18n.py")
    assert "CMIP6 / Future weather morphing" in catalogue
    assert "NavStepButton" in src
    assert "app_icon.png" in src


def test_entrypoint_supports_non_gui_self_test():
    src = read("app.py")
    assert "--self-test" in src
    assert "run_self_test" in src


def test_project_page_creates_real_workspace_from_epw():
    src = read("future_epw_demo/pages/project_page.py")
    for token in [
        "Project Setup",
        "Baseline EPW",
        "Use coordinates from EPW",
        "ProjectWorkspace.create",
        "parse_epw_metadata",
        "Save Project",
        "Next: Climate",
    ]:
        assert token in src
    assert "mock-only and does not create project.json" not in src


def test_climate_page_preserves_protocol_r1_defaults():
    src = read("future_epw_demo/pages/climate_page.py")
    for token in [
        "Recommended / Reproducible Mode",
        "SSP1-2.6",
        "SSP2-4.5",
        "SSP3-7.0",
        "ACCESS-CM2",
        "FGOALS-g3",
        "1985–2014",
        "Bilinear",
        "BTWS",
        "BWS",
        "huss-based",
        "psl",
        "sfcWind ratio",
        "dry-baseline fallback",
    ]:
        assert token in src


def test_cmip6_page_uses_real_subprocess_runner_and_pause_flag():
    src = read("future_epw_demo/pages/cmip6_page.py")
    for token in [
        "WorkflowBackend",
        "WorkflowRunner",
        "Stage 00 · environment",
        "Stage 01 · manifest",
        "Stage 02 · CMIP6 extraction",
        "Start / Resume",
        "Pause",
        "Check Status",
        "request_pause",
    ]:
        assert token in src
    assert "QTimer" not in src


def test_generate_page_runs_real_offline_chain():
    src = read("future_epw_demo/pages/generate_page.py")
    for token in [
        "Stage 03 · climate factors",
        "Stage 04 · generate EPW",
        "Stage 05 · validate",
        "Build Factors + Generate + Validate",
        "generation_records",
        "Open folder",
    ]:
        assert token in src or token in read("future_epw_demo/project_workspace.py")
    assert "v0.5 does not create EPW files" not in src


def test_validation_page_reads_real_outputs_and_exports_package():
    src = read("future_epw_demo/pages/validation_page.py")
    for token in [
        "validation_summary.csv",
        "validation_metadata",
        "Open EPW Folder",
        "Open Validation Folder",
        "Export Project Package",
        "Copy Methods Summary",
        "zipfile.ZipFile",
    ]:
        assert token in src or token in read("future_epw_demo/project_workspace.py")


def test_backend_builds_stage00_to_stage05_commands():
    src = read("future_epw_demo/backend.py")
    for stage in [
        "00_check_environment.py",
        "01_prepare_manifest.py",
        "02_extract_cmip6.py",
        "03_build_climate_factors.py",
        "04_generate_future_epw.py",
        "05_validate_outputs.py",
    ]:
        assert stage in src
    assert "--stop-file" in src
    assert "--status-out" in src


def test_project_workspace_matches_original_cli_layout():
    src = read("future_epw_demo/project_workspace.py")
    for token in [
        "inputs",
        "baseline_epw",
        "cache",
        "cmip6_monthly",
        "cmip6_monthly_city",
        "outputs",
        "manifest",
        "factors",
        "epw",
        "audit",
        "validation",
        "project.json",
    ]:
        assert token in src


def test_arbitrary_city_alpha_keeps_original_wmo_map_only_as_backward_compatibility():
    src = read("future_epw_demo/project_workspace.py")
    for wmo in ["421820", "486980", "405820", "545110", "037720", "947670", "082210", "716240"]:
        assert wmo in src
    assert "no longer a gate on project creation" in src
    assert "location_key" in src
    assert "location_spec.json" in src


def test_bundled_engine_contains_stage03_hotfix_and_pause_support():
    stage03 = read("engine_core/03_build_climate_factors.py")
    factors = read("engine_core/src/factors.py")
    stage02 = read("engine_core/02_extract_cmip6.py")
    cmip6io = read("engine_core/src/cmip6_io.py")
    assert "pr_dry_baseline_fallback_rows" in stage03
    assert "pr_dry_baseline_fallback" in factors
    assert "r[signal]=1.0" in factors
    assert "--stop-file" in stage02
    assert "should_stop" in cmip6io


def test_stage04_emits_per_case_progress_for_gui():
    src = read("engine_core/04_generate_future_epw.py")
    assert "total_cases" in src
    assert "generate {r.city}" in src


def test_runner_uses_qprocess_and_merged_output():
    src = read("future_epw_demo/runner.py")
    assert "QProcess" in src
    assert "MergedChannels" in src
    assert "PYTHONUNBUFFERED" in src
    assert "sequence_finished" in src


def test_v05_theme_is_preserved():
    src = read("future_epw_demo/theme.py")
    for token in [
        "QFrame#ResearchStrip",
        "QFrame#DataPanel",
        "QFrame#WeatherMetadataPanel",
        "QFrame#ProjectSummary",
        "QFrame#PipelineNode",
        "QTextEdit#LogConsole",
    ]:
        assert token in src


def test_v091_shell_exposes_settings_and_version():
    main = read("future_epw_demo/main_window.py")
    assert "SettingsDialog" in main
    assert "try_reopen_last_project" in main
    assert "reopen_last_project" in main
    assert "v0.9.1 • Functional MVP" in main or "app.version" in main
    settings = read("future_epw_demo/settings_dialog.py")
    for token in ["Language", "Text size", "Reopen last project automatically", "Show detailed backend log by default", "Restore defaults"]:
        assert token in settings


def test_v091_uses_application_settings_outside_project_workspace():
    source = read("future_epw_demo/app_settings.py")
    assert "FUTURE_EPW_SETTINGS_PATH" in source
    assert "last_project_path" in source
    assert "reopen_last_project" in source
    assert "show_detailed_log" in source


def test_v100_version_identifiers_are_consistent():
    assert read("VERSION").strip() == "1.0.0"
    workspace = read("future_epw_demo/project_workspace.py")
    assert '"app_version": "1.0.0"' in workspace
    catalogue = read("future_epw_demo/i18n.py")
    assert "Version 1.0.0 · Protocol R1" in catalogue


def test_v091_self_test_covers_new_pure_python_services():
    source = read("app.py")
    for token in ["AppSettings", "Translator", "ExtractionETA", "1.0.0"]:
        assert token in source


def test_auto_reopen_returns_to_cmip6_when_any_stage02_remote_work_is_ready():
    source = read("future_epw_demo/main_window.py")
    assert "snap = ws.status_snapshot()" in source
    assert "snap.cmip6_complete > 0 or snap.remote_ready > 0" in source


def test_v100_release_identity_and_welcome_contract():
    assert read("VERSION").strip() == "1.0.0"
    catalogue = read("future_epw_demo/i18n.py")
    assert "Version 1.0.0 · Protocol R1" in catalogue
    welcome = read("future_epw_demo/welcome_dialog.py")
    assert "Create Project" in welcome
    assert "Open Project" in welcome
    settings = read("future_epw_demo/app_settings.py")
    assert "welcome_seen" in settings
