from pathlib import Path
import json

from future_epw_demo.demo_state import WorkflowState, dynamic_asset_total, expected_epw_count
from future_epw_demo.project_workspace import ProjectWorkspace
from tests.test_functional_backend import make_epw


def test_advanced_selection_counts_20_assets_and_2_epws():
    state = WorkflowState(
        climate_mode="advanced",
        scenarios=["ssp126"],
        periods=["2040"],
        gcms=["ACCESS-CM2"],
        cities=["Tokyo"],
    )
    assert dynamic_asset_total(state) == 20
    assert expected_epw_count(state) == 2


def test_project_persists_climate_selection_and_dynamic_total(tmp_path: Path):
    epw = make_epw(tmp_path / "tokyo.epw", wmo="476710", lat=35.5533, lon=139.7811)
    lines = epw.read_text(encoding="utf-8").splitlines()
    lines[0] = "LOCATION,Tokyo.Intl.AP-Haneda.AP,TK,JPN,SRC-TMYx,476710,35.5533,139.7811,9.0,10.7"
    epw.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ws = ProjectWorkspace.create(
        root=tmp_path / "project", project_name="Tokyo", city_name="Tokyo", baseline_source=epw,
        scenarios=["ssp126"], periods=["2040"], gcms=["ACCESS-CM2"], climate_mode="advanced",
    )
    payload = json.loads(ws.project_file.read_text(encoding="utf-8"))
    assert payload["climate_selection"]["mode"] == "advanced"
    assert payload["climate_selection"]["gcms"] == ["ACCESS-CM2"]
    assert payload["climate_selection"]["ssps"] == ["ssp126"]
    assert payload["climate_selection"]["periods"] == [2040]
    assert ws.dynamic_asset_total() == 20
    assert ws.expected_epw_count() == 2


def test_old_project_without_climate_selection_loads_as_reproducible(tmp_path: Path):
    epw = make_epw(tmp_path / "source.epw")
    ws = ProjectWorkspace.create(
        root=tmp_path / "project", project_name="Old", baseline_source=epw,
        scenarios=["ssp126", "ssp245", "ssp370"], periods=["2040", "2060"],
        gcms=["ACCESS-CM2", "GFDL-ESM4", "MPI-ESM1-2-HR", "IPSL-CM6A-LR", "FGOALS-g3"],
    )
    payload = json.loads(ws.project_file.read_text(encoding="utf-8"))
    payload.pop("climate_selection", None)
    ws.project_file.write_text(json.dumps(payload), encoding="utf-8")
    loaded = ProjectWorkspace.load(ws.root)
    assert loaded.climate_mode == "reproducible"
    assert loaded.dynamic_asset_total() == 200


def test_backend_passes_dynamic_selection_to_stage01_and_stage03(tmp_path: Path):
    from future_epw_demo.backend import WorkflowBackend
    epw = make_epw(tmp_path / "source.epw")
    ws = ProjectWorkspace.create(
        root=tmp_path / "project2", project_name="A", baseline_source=epw,
        scenarios=["ssp126"], periods=["2040"], gcms=["ACCESS-CM2"], climate_mode="advanced",
    )
    engine = tmp_path / "engine"
    engine.mkdir()
    for name in ["00_check_environment.py", "01_prepare_manifest.py", "02_extract_cmip6.py", "03_build_climate_factors.py", "04_generate_future_epw.py", "05_validate_outputs.py"]:
        (engine / name).write_text("", encoding="utf-8")
    (engine / "inputs" / "catalog").mkdir(parents=True)
    (engine / "inputs" / "catalog" / "catalog_subset_205_assets.csv").write_text("x\n", encoding="utf-8")
    commands = WorkflowBackend(engine_dir=engine, python_executable="py").commands(ws)
    assert commands.stage01[commands.stage01.index("--models") + 1:] [:1] == ["ACCESS-CM2"]
    assert "--experiments" in commands.stage01
    assert "historical" in commands.stage01 and "ssp126" in commands.stage01
    assert "--periods" in commands.stage01 and "2040" in commands.stage01
    assert "--models" in commands.stage03 and "ACCESS-CM2" in commands.stage03
    assert "--scenarios" in commands.stage03 and "ssp126" in commands.stage03
    assert "--labels" in commands.stage03 and "2040" in commands.stage03


def test_dynamic_status_counts_only_assets_in_current_selection(tmp_path: Path):
    epw = make_epw(tmp_path / "source2.epw")
    ws = ProjectWorkspace.create(
        root=tmp_path / "project3", project_name="A", baseline_source=epw,
        scenarios=["ssp126"], periods=["2040"], gcms=["ACCESS-CM2"], climate_mode="advanced",
    )
    (ws.cache_dir / "ACCESS-CM2__historical__tas.csv").write_text("x\n", encoding="utf-8")
    (ws.cache_dir / "ACCESS-CM2__ssp126__tas.csv").write_text("x\n", encoding="utf-8")
    # A reusable cache from another selection must not inflate this project's denominator/progress.
    (ws.cache_dir / "GFDL-ESM4__ssp370__tas.csv").write_text("x\n", encoding="utf-8")
    snap = ws.status_snapshot()
    assert snap.cmip6_total == 20
    assert snap.cmip6_complete == 2
    assert snap.cmip6_missing == 18


def test_changing_selection_invalidates_derived_outputs_but_keeps_cache(tmp_path: Path):
    epw = make_epw(tmp_path / "source3.epw")
    ws = ProjectWorkspace.create(
        root=tmp_path / "project4", project_name="A", baseline_source=epw,
        scenarios=["ssp126"], periods=["2040"], gcms=["ACCESS-CM2"], climate_mode="advanced",
    )
    (ws.cache_dir / "ACCESS-CM2__historical__tas.csv").write_text("cache\n", encoding="utf-8")
    ws.manifest_file.parent.mkdir(parents=True, exist_ok=True)
    ws.manifest_file.write_text("a\n1\n", encoding="utf-8")
    ws.factors_dir.mkdir(parents=True, exist_ok=True)
    (ws.factors_dir / "x.txt").write_text("derived", encoding="utf-8")
    changed = ws.update_climate_selection(
        mode="advanced", scenarios=["ssp126", "ssp245"], periods=["2040"], gcms=["ACCESS-CM2"]
    )
    assert changed is True
    assert (ws.cache_dir / "ACCESS-CM2__historical__tas.csv").exists()
    assert not ws.manifest_file.exists()
    assert not (ws.factors_dir / "x.txt").exists()
    archived = list((ws.outputs_dir / "stale").rglob("x.txt"))
    assert len(archived) == 1
    assert archived[0].read_text(encoding="utf-8") == "derived"


def test_cmip6_page_uses_dynamic_manifest_contract():
    source = Path("future_epw_demo/pages/cmip6_page.py").read_text(encoding="utf-8")
    assert "ws.manifest_matches_selection()" in source
    assert 'count=200' not in source
    assert 'QLabel("200")' not in source
    assert '0 / 200' not in source


def test_workflow_state_reconciles_completed_dynamic_stage02(tmp_path: Path):
    import json
    from future_epw_demo.workflow_state import WorkflowStateStore
    epw = make_epw(tmp_path / "dynamic_state.epw")
    ws = ProjectWorkspace.create(
        root=tmp_path / "dynamic_state_project", project_name="Tokyo", baseline_source=epw,
        city_name="Tokyo", scenarios=["ssp126"], periods=["2040"],
        gcms=["ACCESS-CM2"], climate_mode="advanced",
    )
    # Filesystem evidence is authoritative for the active 20-asset selection.
    for key in sorted(ws.expected_asset_keys()):
        (ws.cache_dir / f"{key}.csv").write_text("x\n", encoding="utf-8")
    ws.cmip6_status_file.write_text(json.dumps({
        "total": 20, "complete_assets": 20, "cached": 20,
        "cities": [ws.city],
        "locations": [{"city": ws.city, "latitude": ws.latitude, "longitude": ws.longitude}],
    }), encoding="utf-8")
    record = WorkflowStateStore(ws).reconcile(active_process=False)
    assert record.cmip6_total == 20
    assert record.cmip6_complete == 20
    assert record.current_stage == "stage03"
    assert record.last_successful_stage == "stage02"
    assert record.state == "ready"


def test_runtime_navigation_does_not_require_fixed_200_assets():
    main_source = Path("future_epw_demo/main_window.py").read_text(encoding="utf-8")
    workflow_source = Path("future_epw_demo/workflow_state.py").read_text(encoding="utf-8")
    assert "self.state.cmip6_total == 200" not in main_source
    assert "snap.cmip6_total == 200" not in workflow_source
    assert "snap.cmip6_complete == 200" not in workflow_source
