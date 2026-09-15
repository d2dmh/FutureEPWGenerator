from pathlib import Path

from future_epw_demo.workflow_state import WorkflowStateRecord, WorkflowStateStore
from future_epw_demo.project_workspace import ProjectWorkspace
from tests.test_functional_backend import make_epw


def make_ws(tmp_path: Path) -> ProjectWorkspace:
    epw = make_epw(tmp_path / "source.epw")
    return ProjectWorkspace.create(
        root=tmp_path / "project", project_name="Test", baseline_source=epw,
        scenarios=["ssp126", "ssp245", "ssp370"], periods=["2040", "2060"],
        gcms=["ACCESS-CM2", "GFDL-ESM4", "MPI-ESM1-2-HR", "IPSL-CM6A-LR", "FGOALS-g3"],
    )


def test_state_round_trip(tmp_path: Path):
    ws = make_ws(tmp_path)
    store = WorkflowStateStore(ws)
    record = WorkflowStateRecord(current_stage="stage02", state="paused", cmip6_complete=73)
    store.save(record)
    assert store.load().cmip6_complete == 73
    assert store.load().state == "paused"


def test_stale_running_becomes_paused_after_restart(tmp_path: Path):
    ws = make_ws(tmp_path)
    store = WorkflowStateStore(ws)
    store.save(WorkflowStateRecord(current_stage="stage02", state="running", cmip6_complete=0))
    reconciled = store.reconcile(active_process=False)
    assert reconciled.state == "paused"


def test_reconcile_uses_real_partial_cmip6_progress(tmp_path: Path):
    ws = make_ws(tmp_path)
    for i in range(73):
        (ws.cache_dir / f"asset_{i}.csv").write_text("x\n", encoding="utf-8")
    reconciled = WorkflowStateStore(ws).reconcile(active_process=False)
    assert reconciled.cmip6_complete == 73
    assert reconciled.cmip6_total == 200


def test_factor_metadata_alone_is_not_complete(tmp_path: Path):
    ws = make_ws(tmp_path)
    ws.factor_metadata_file.write_text('{"pr_dry_baseline_fallback_rows": 0}', encoding="utf-8")
    assert ws.factors_complete() is False


def test_generation_requires_records_and_all_output_files(tmp_path: Path):
    ws = make_ws(tmp_path)
    ws.generation_records_file.write_text("output_epw\nmissing.epw\n", encoding="utf-8")
    assert ws.generation_complete() is False


def test_failed_validation_is_not_complete_success(tmp_path: Path):
    ws = make_ws(tmp_path)
    ws.validation_metadata_file.write_text('{"epw_count": 36, "audit_groups": 360, "passed": false}', encoding="utf-8")
    assert ws.validation_outcome() == "fail"


def test_expected_epw_count_uses_project_configuration(tmp_path: Path):
    ws = make_ws(tmp_path)
    assert ws.expected_epw_count() == 36


def test_complete_artifacts_reconcile_to_pass(tmp_path: Path):
    import csv, json
    ws = make_ws(tmp_path)
    # Complete Stage 02 status.
    ws.cmip6_status_file.write_text(json.dumps({
        "current_city_total": 200, "current_city_complete": 200,
        "cities": [ws.city],
        "locations": [{"city": ws.city, "latitude": ws.latitude, "longitude": ws.longitude}],
    }), encoding="utf-8")
    # Complete Stage 03 artifact set.
    for name in ["monthly_climatology_long.csv", "climate_factors_per_gcm.csv", "climate_factors_ensemble.csv"]:
        (ws.factors_dir / name).write_text("x\n1\n", encoding="utf-8")
    ws.factor_metadata_file.write_text(json.dumps({"pr_dry_baseline_fallback_rows": 0}), encoding="utf-8")
    # Complete Stage 04 records and files.
    rows=[]
    for i in range(ws.expected_epw_count()):
        out = ws.epw_dir / ws.city / f"case_{i}.epw"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("epw", encoding="utf-8")
        rows.append(str(out))
    with ws.generation_records_file.open("w", encoding="utf-8", newline="") as handle:
        writer=csv.writer(handle); writer.writerow(["output_epw"]); writer.writerows([[x] for x in rows])
    ws.validation_metadata_file.write_text(json.dumps({"epw_count": ws.expected_epw_count(), "audit_groups": 360, "passed": True}), encoding="utf-8")
    assert ws.factors_complete() is True
    assert ws.generation_complete() is True
    assert ws.validation_outcome() == "pass"
    record = WorkflowStateStore(ws).reconcile(active_process=False)
    assert record.state == "complete"
    assert record.last_successful_stage == "stage05"
