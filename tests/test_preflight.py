from pathlib import Path
import json

from future_epw_demo.preflight import run_generation_preflight
from future_epw_demo.project_workspace import ProjectWorkspace
from tests.test_functional_backend import make_epw


def make_preflight_ws(tmp_path: Path, *, cmip6_complete: int) -> ProjectWorkspace:
    epw = make_epw(tmp_path / "source.epw")
    ws = ProjectWorkspace.create(
        root=tmp_path / "project", project_name="Test", baseline_source=epw,
        scenarios=["ssp126", "ssp245", "ssp370"], periods=["2040", "2060"],
        gcms=["ACCESS-CM2", "GFDL-ESM4", "MPI-ESM1-2-HR", "IPSL-CM6A-LR", "FGOALS-g3"],
    )
    ws.manifest_file.write_text("asset\n" + "\n".join(str(i) for i in range(200)) + "\n", encoding="utf-8")
    ws.cmip6_status_file.write_text(json.dumps({
        "current_city_total": 200,
        "current_city_complete": cmip6_complete,
        "cities": [ws.city],
        "locations": [{"city": ws.city, "latitude": ws.latitude, "longitude": ws.longitude}],
    }), encoding="utf-8")
    return ws


def test_preflight_blocks_incomplete_cmip6(tmp_path: Path):
    ws = make_preflight_ws(tmp_path, cmip6_complete=199)
    report = run_generation_preflight(ws)
    assert report.passed is False
    assert report.as_dict()["CMIP6 cache"].passed is False


def test_preflight_blocks_baseline_hash_mismatch(tmp_path: Path):
    ws = make_preflight_ws(tmp_path, cmip6_complete=200)
    ws.baseline_path.write_text(ws.baseline_path.read_text(encoding="utf-8") + "changed", encoding="utf-8")
    report = run_generation_preflight(ws)
    assert report.passed is False
    assert report.as_dict()["Baseline EPW"].passed is False


def test_preflight_passes_valid_complete_inputs(tmp_path: Path):
    ws = make_preflight_ws(tmp_path, cmip6_complete=200)
    report = run_generation_preflight(ws)
    assert report.passed is True
    assert [c.name for c in report.checks] == [
        "Project", "Baseline EPW", "Location", "Protocol R1", "Climate selection", "Manifest", "CMIP6 cache", "Output directory", "Workflow idle"
    ]


def test_preflight_checks_expose_stable_localization_keys(tmp_path: Path):
    ws = make_preflight_ws(tmp_path, cmip6_complete=0)
    report = run_generation_preflight(ws, process_active=False)
    keys = [check.key for check in report.checks]
    assert keys == ["project", "baseline", "location", "protocol", "selection", "manifest", "cache", "output", "idle"]
    assert len(set(keys)) == len(keys)


def test_preflight_blocks_empty_advanced_selection(tmp_path: Path):
    epw = make_epw(tmp_path / "empty.epw")
    ws = ProjectWorkspace.create(
        root=tmp_path / "empty_project", project_name="Empty", baseline_source=epw,
        scenarios=[], periods=[], gcms=[], climate_mode="advanced",
    )
    report = run_generation_preflight(ws)
    assert report.passed is False
    check = report.as_dict()["Climate selection"]
    assert check.passed is False
    assert check.key == "selection"
