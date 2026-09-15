from pathlib import Path


def read(rel: str) -> str:
    return Path(rel).read_text(encoding="utf-8")


def test_project_page_exposes_open_existing_project_action():
    source = read("future_epw_demo/pages/project_page.py")
    assert "Open Existing Project" in source
    assert "ProjectWorkspace.load" in source
    assert "WorkflowUserError" in source
    assert "active_workspace" in source


def test_main_window_still_activates_workspace_through_project_saved():
    source = read("future_epw_demo/main_window.py")
    assert "def _project_saved" in source
    assert "self.workspace = ws" in source


def test_retry_failed_reuses_resume_path():
    source = read("future_epw_demo/pages/cmip6_page.py")
    assert "def retry_failed" in source
    assert "self.resume()" in source
    assert "self.refresh_from_workspace()" in source


def test_cmip6_page_uses_workflow_state_store():
    source = read("future_epw_demo/pages/cmip6_page.py")
    assert "WorkflowStateStore" in source
    assert 'current_stage="stage02"' in source
    assert "failure_reported" in source


def test_generate_page_imports_explicit_preflight():
    source = read("future_epw_demo/pages/generate_page.py")
    assert "run_generation_preflight" in source
    assert "report.passed" in source
    for label in ["Project", "Baseline EPW", "Location", "Protocol R1", "Manifest", "CMIP6 cache", "Output directory", "Workflow idle"]:
        assert label in source


def test_generate_success_is_reconciled_from_workspace_not_exit_code_only():
    source = read("future_epw_demo/pages/generate_page.py")
    assert "WorkflowStateStore" in source
    assert "reconcile" in source
    assert "ws.generation_complete()" in source
    assert "ws.validation_outcome()" in source


def test_main_window_reconciles_persistent_state():
    source = read("future_epw_demo/main_window.py")
    assert "WorkflowStateStore" in source
    assert ".reconcile(" in source
    assert "app.version" in source
    assert "Version 1.0.0 · Protocol R1" in read("future_epw_demo/i18n.py")


def test_validation_page_uses_workspace_truth():
    source = read("future_epw_demo/pages/validation_page.py")
    assert "ws.expected_epw_count()" in source
    assert "ws.validation_outcome()" in source
