from __future__ import annotations

import json
from pathlib import Path

import pytest

from future_epw_demo.backend import BackendPaths, WorkflowBackend
from future_epw_demo.epw_meta import parse_epw_metadata
from future_epw_demo.project_workspace import ProjectWorkspace, SUPPORTED_WMO_TO_CITY


def make_epw(path: Path, *, wmo: str = "486980", lat: float = 1.3678, lon: float = 103.9826) -> Path:
    header = [
        f"LOCATION,Singapore-Changi.Intl.AP,SG,SGP,SRC-TMYx,{wmo},{lat},{lon},8.0,6.7",
        "DESIGN CONDITIONS,0",
        "TYPICAL/EXTREME PERIODS,0",
        "GROUND TEMPERATURES,0",
        "HOLIDAYS/DAYLIGHT SAVINGS,No,0,0,0",
        "COMMENTS 1,test",
        "COMMENTS 2,test",
        "DATA PERIODS,1,1,Data,Sunday,1/1,12/31",
    ]
    row = "2020,1,1,1,60,0,25,20,60,101325,0,0,300,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0"
    path.write_text("\n".join(header + [row] * 8760) + "\n", encoding="utf-8")
    return path


def test_parse_epw_metadata_reads_station_and_8760_rows(tmp_path: Path):
    epw = make_epw(tmp_path / "sg.epw")
    meta = parse_epw_metadata(epw)
    assert meta.wmo == "486980"
    assert meta.latitude == pytest.approx(1.3678)
    assert meta.longitude == pytest.approx(103.9826)
    assert meta.elevation == pytest.approx(6.7)
    assert meta.hours == 8760
    assert meta.valid is True


def test_project_workspace_creates_cli_compatible_layout_and_project_json(tmp_path: Path):
    epw = make_epw(tmp_path / "source.epw")
    root = tmp_path / "project"
    ws = ProjectWorkspace.create(
        root=root,
        project_name="Singapore_Future_EPW",
        baseline_source=epw,
        scenarios=["ssp126", "ssp245", "ssp370"],
        periods=["2040", "2060"],
        gcms=["ACCESS-CM2", "GFDL-ESM4", "MPI-ESM1-2-HR", "IPSL-CM6A-LR", "FGOALS-g3"],
    )
    assert ws.city == "Singapore"
    assert (root / "inputs" / "baseline_epw" / "source.epw").exists()
    for rel in [
        "cache/cmip6_monthly",
        "cache/cmip6_monthly_city",
        "outputs/manifest",
        "outputs/factors",
        "outputs/epw",
        "outputs/audit",
        "outputs/validation",
        "logs",
        "runtime",
    ]:
        assert (root / rel).is_dir()
    payload = json.loads((root / "project.json").read_text(encoding="utf-8"))
    assert payload["city"] == "Singapore"
    assert payload["wmo"] == "486980"
    assert payload["workflow_protocol"] == "R1"


def test_project_workspace_accepts_nonregistry_wmo_with_explicit_city_label(tmp_path: Path):
    epw = make_epw(tmp_path / "other.epw", wmo="999999")
    ws = ProjectWorkspace.create(
        root=tmp_path / "project",
        project_name="Other",
        city_name="New City",
        baseline_source=epw,
        scenarios=["ssp126"],
        periods=["2040"],
        gcms=["ACCESS-CM2"],
    )
    assert ws.city == "New City"
    assert ws.metadata.wmo == "999999"


def test_supported_wmo_map_contains_all_eight_production_cities():
    assert len(SUPPORTED_WMO_TO_CITY) == 8
    assert SUPPORTED_WMO_TO_CITY["486980"] == "Singapore"
    assert SUPPORTED_WMO_TO_CITY["545110"] == "Beijing"


def test_backend_builds_real_stage_commands(tmp_path: Path):
    epw = make_epw(tmp_path / "source.epw")
    ws = ProjectWorkspace.create(
        root=tmp_path / "project",
        project_name="Singapore_Future_EPW",
        baseline_source=epw,
        scenarios=["ssp126", "ssp245", "ssp370"],
        periods=["2040", "2060"],
        gcms=["ACCESS-CM2", "GFDL-ESM4", "MPI-ESM1-2-HR", "IPSL-CM6A-LR", "FGOALS-g3"],
    )
    engine = tmp_path / "engine"
    engine.mkdir()
    for name in ["00_check_environment.py", "01_prepare_manifest.py", "02_extract_cmip6.py", "03_build_climate_factors.py", "04_generate_future_epw.py", "05_validate_outputs.py"]:
        (engine / name).write_text("", encoding="utf-8")
    (engine / "inputs" / "catalog").mkdir(parents=True)
    (engine / "inputs" / "catalog" / "catalog_subset_205_assets.csv").write_text("x\n", encoding="utf-8")

    backend = WorkflowBackend(engine_dir=engine, python_executable="python-test")
    commands = backend.commands(ws)
    assert commands.stage00[0] == "python-test"
    assert "--epw-dir" in commands.stage00 and str(ws.baseline_dir) in commands.stage00
    assert "--cities" in commands.stage02 and "Singapore" in commands.stage02
    assert "--stop-file" in commands.stage02
    assert str(ws.manifest_file) in commands.stage03
    assert "--selectors" in commands.stage04 and "mean" in commands.stage04
    assert str(ws.validation_dir) in commands.stage05


def test_backend_reads_status_files_into_workspace_state(tmp_path: Path):
    epw = make_epw(tmp_path / "source.epw")
    ws = ProjectWorkspace.create(
        root=tmp_path / "project",
        project_name="Singapore_Future_EPW",
        baseline_source=epw,
        scenarios=["ssp126", "ssp245", "ssp370"],
        periods=["2040", "2060"],
        gcms=["ACCESS-CM2", "GFDL-ESM4", "MPI-ESM1-2-HR", "IPSL-CM6A-LR", "FGOALS-g3"],
    )
    ws.cmip6_status_file.write_text(json.dumps({"total": 200, "cached": 17, "missing": 183, "complete_assets": 17, "pending_assets": 183, "city_cached_within_pending_assets": 3, "city_slots_within_pending_assets": 183, "cities": ["Singapore"]}), encoding="utf-8")
    ws.factor_metadata_file.parent.mkdir(parents=True, exist_ok=True)
    ws.factor_metadata_file.write_text(json.dumps({"climatology_rows": 4200, "per_gcm_rows": 360, "ensemble_rows": 360, "pr_dry_baseline_fallback_rows": 0}), encoding="utf-8")
    ws.validation_metadata_file.parent.mkdir(parents=True, exist_ok=True)
    ws.validation_metadata_file.write_text(json.dumps({"epw_count": 36, "audit_groups": 360, "passed": True}), encoding="utf-8")

    snap = ws.status_snapshot()
    assert snap.cmip6_complete == 17
    assert snap.city_cached == 3
    assert snap.remote_ready == 20
    assert snap.cmip6_total == 200
    assert snap.factors_ready is True
    assert snap.epw_count == 36
    assert snap.validation_passed is True


def test_status_snapshot_discovers_existing_cli_cache_without_status_file(tmp_path: Path):
    epw = make_epw(tmp_path / "source.epw")
    ws = ProjectWorkspace.create(
        root=tmp_path / "project",
        project_name="Singapore_Future_EPW",
        baseline_source=epw,
        scenarios=["ssp126", "ssp245", "ssp370"],
        periods=["2040", "2060"],
        gcms=["ACCESS-CM2", "GFDL-ESM4", "MPI-ESM1-2-HR", "IPSL-CM6A-LR", "FGOALS-g3"],
    )
    ws.manifest_file.write_text("a\n" + "\n".join(str(i) for i in range(200)) + "\n", encoding="utf-8")
    for i in range(7):
        (ws.cache_dir / f"asset_{i}.csv").write_text("x\n", encoding="utf-8")
    snap = ws.status_snapshot()
    assert snap.cmip6_total == 200
    assert snap.cmip6_complete == 7
    assert snap.cmip6_missing == 193


def test_status_snapshot_does_not_double_count_complete_assets_and_city_checkpoints(tmp_path: Path):
    epw = make_epw(tmp_path / "source.epw")
    ws = ProjectWorkspace.create(
        root=tmp_path / "project", project_name="Singapore", city_name="Singapore", baseline_source=epw,
        scenarios=["ssp126"], periods=["2040"], gcms=["ACCESS-CM2"],
    )
    ws.manifest_file.write_text("a\n" + "\n".join(str(i) for i in range(200)) + "\n", encoding="utf-8")
    for i in range(12):
        stem = f"MODEL{i}__historical__tas"
        (ws.cache_dir / f"{stem}.csv").write_text("x\n", encoding="utf-8")
        (ws.city_cache_dir / f"{stem}__Singapore.csv").write_text("x\n", encoding="utf-8")
    snap = ws.status_snapshot()
    assert snap.cmip6_complete == 12
    assert snap.city_cached == 12
    assert snap.remote_ready == 12
    assert snap.cmip6_missing == 188

def test_project_workspace_accepts_arbitrary_valid_station_and_writes_location_spec(tmp_path: Path):
    epw = make_epw(tmp_path / "paris.epw", wmo="071490", lat=48.7262, lon=2.3652)
    lines = epw.read_text(encoding="utf-8").splitlines()
    lines[0] = "LOCATION,Paris-Orly,IDF,FRA,SRC-TMYx,071490,48.7262,2.3652,1.0,89.0"
    epw.write_text("\n".join(lines) + "\n", encoding="utf-8")

    ws = ProjectWorkspace.create(
        root=tmp_path / "project",
        project_name="Paris_Future_EPW",
        city_name="Paris",
        baseline_source=epw,
        scenarios=["ssp126", "ssp245", "ssp370"],
        periods=["2040", "2060"],
        gcms=["ACCESS-CM2", "GFDL-ESM4", "MPI-ESM1-2-HR", "IPSL-CM6A-LR", "FGOALS-g3"],
    )

    assert ws.city == "Paris"
    assert ws.metadata.wmo == "071490"
    assert ws.location_key.startswith("Paris__")
    assert ws.cache_dir.parent.parent.name == "locations"
    assert ws.location_spec_file.exists()
    spec = json.loads(ws.location_spec_file.read_text(encoding="utf-8"))
    assert spec["locations"][0]["city"] == "Paris"
    assert spec["locations"][0]["latitude"] == pytest.approx(48.7262)
    assert spec["locations"][0]["longitude"] == pytest.approx(2.3652)
    assert Path(spec["locations"][0]["baseline_epw"]).resolve() == (ws.baseline_dir / ws.baseline_filename).resolve()


def test_location_specific_cache_namespace_prevents_other_city_cache_false_positive(tmp_path: Path):
    epw1 = make_epw(tmp_path / "sg.epw")
    sg = ProjectWorkspace.create(
        root=tmp_path / "project",
        project_name="SG",
        city_name="Singapore",
        baseline_source=epw1,
        scenarios=["ssp126"], periods=["2040"], gcms=["ACCESS-CM2"],
    )
    sg.cache_dir.mkdir(parents=True, exist_ok=True)
    (sg.cache_dir / "already.csv").write_text("x\n", encoding="utf-8")

    epw2 = make_epw(tmp_path / "paris.epw", wmo="071490", lat=48.7262, lon=2.3652)
    lines = epw2.read_text(encoding="utf-8").splitlines()
    lines[0] = "LOCATION,Paris-Orly,IDF,FRA,SRC-TMYx,071490,48.7262,2.3652,1.0,89.0"
    epw2.write_text("\n".join(lines) + "\n", encoding="utf-8")
    meta2 = parse_epw_metadata(epw2)
    # v0.9 correctly forbids creating a second project over the same project.json.
    # Construct a second workspace identity at the same root only to test the
    # location-key namespace itself without mutating the saved project.
    paris = ProjectWorkspace(
        root=sg.root, project_name="Paris", city="Paris", metadata=meta2,
        baseline_filename=epw2.name, latitude=meta2.latitude, longitude=meta2.longitude,
        coordinate_source="epw", scenarios=["ssp126"], periods=["2040"], gcms=["ACCESS-CM2"],
    )

    assert paris.cache_dir != sg.cache_dir
    assert list(paris.cache_dir.glob("*.csv")) == []


def test_backend_passes_explicit_location_spec_to_arbitrary_city_stages(tmp_path: Path):
    epw = make_epw(tmp_path / "paris.epw", wmo="071490", lat=48.7262, lon=2.3652)
    lines = epw.read_text(encoding="utf-8").splitlines()
    lines[0] = "LOCATION,Paris-Orly,IDF,FRA,SRC-TMYx,071490,48.7262,2.3652,1.0,89.0"
    epw.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ws = ProjectWorkspace.create(
        root=tmp_path / "project", project_name="Paris", city_name="Paris", baseline_source=epw,
        scenarios=["ssp126", "ssp245", "ssp370"], periods=["2040", "2060"],
        gcms=["ACCESS-CM2", "GFDL-ESM4", "MPI-ESM1-2-HR", "IPSL-CM6A-LR", "FGOALS-g3"],
    )
    engine = tmp_path / "engine"
    engine.mkdir()
    for name in ["00_check_environment.py", "01_prepare_manifest.py", "02_extract_cmip6.py", "03_build_climate_factors.py", "04_generate_future_epw.py", "05_validate_outputs.py"]:
        (engine / name).write_text("", encoding="utf-8")
    (engine / "inputs" / "catalog").mkdir(parents=True)
    (engine / "inputs" / "catalog" / "catalog_subset_205_assets.csv").write_text("x\n", encoding="utf-8")
    commands = WorkflowBackend(engine_dir=engine, python_executable="python-test").commands(ws)
    for command in [commands.stage00, commands.stage02, commands.stage02_status, commands.stage04]:
        assert "--location-spec" in command
        assert str(ws.location_spec_file) in command
    assert "Paris" in commands.stage03


def test_project_workspace_can_use_explicit_target_coordinates_separate_from_epw_station(tmp_path: Path):
    epw = make_epw(tmp_path / "paris_orly.epw", wmo="071490", lat=48.7262, lon=2.3652)
    lines = epw.read_text(encoding="utf-8").splitlines()
    lines[0] = "LOCATION,Paris-Orly,IDF,FRA,SRC-TMYx,071490,48.7262,2.3652,1.0,89.0"
    epw.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ws = ProjectWorkspace.create(
        root=tmp_path / "project", project_name="Paris", city_name="Paris", baseline_source=epw,
        latitude=48.8566, longitude=2.3522, use_epw_coordinates=False,
        scenarios=["ssp126"], periods=["2040"], gcms=["ACCESS-CM2"],
    )
    assert ws.latitude == pytest.approx(48.8566)
    assert ws.longitude == pytest.approx(2.3522)
    spec = json.loads(ws.location_spec_file.read_text(encoding="utf-8"))["locations"][0]
    assert spec["coordinate_source"] == "manual"
    assert spec["latitude"] == pytest.approx(48.8566)
    assert spec["baseline_latitude"] == pytest.approx(48.7262)


def test_status_snapshot_ignores_status_file_from_another_location(tmp_path: Path):
    epw = make_epw(tmp_path / "source.epw")
    ws = ProjectWorkspace.create(
        root=tmp_path / "project", project_name="Singapore", city_name="Singapore", baseline_source=epw,
        scenarios=["ssp126"], periods=["2040"], gcms=["ACCESS-CM2"],
    )
    ws.cmip6_status_file.write_text(json.dumps({
        "total": 200, "current_city_total": 200, "current_city_complete": 200,
        "cities": ["Paris"], "locations": [{"city":"Paris","latitude":48.8566,"longitude":2.3522}],
    }), encoding="utf-8")
    snap = ws.status_snapshot()
    assert snap.cmip6_complete == 0
    assert snap.cmip6_missing == 200


def test_status_snapshot_prefers_real_asset_files_over_stale_overcounted_status(tmp_path: Path):
    epw = make_epw(tmp_path / "source.epw")
    ws = ProjectWorkspace.create(
        root=tmp_path / "project", project_name="Singapore", city_name="Singapore", baseline_source=epw,
        scenarios=["ssp126"], periods=["2040"], gcms=["ACCESS-CM2"],
    )
    ws.manifest_file.write_text("a\n" + "\n".join(str(i) for i in range(200)) + "\n", encoding="utf-8")
    for i in range(12):
        stem = f"MODEL{i}__historical__tas"
        (ws.cache_dir / f"{stem}.csv").write_text("x\n", encoding="utf-8")
        (ws.city_cache_dir / f"{stem}__Singapore.csv").write_text("x\n", encoding="utf-8")
    # Simulates a stale v0.9 status snapshot that incorrectly treated checkpoint
    # progress as completed asset progress.
    ws.cmip6_status_file.write_text(json.dumps({
        "total": 200,
        "cached": 24,
        "complete_assets": 24,
        "city_cached_within_pending_assets": 0,
        "cities": ["Singapore"],
        "locations": [{"city": "Singapore", "latitude": ws.latitude, "longitude": ws.longitude}],
    }), encoding="utf-8")

    snap = ws.status_snapshot()
    assert snap.cmip6_complete == 12
    assert snap.remote_ready == 12
    assert snap.cmip6_missing == 188


def test_status_json_keeps_completed_assets_separate_from_pending_city_checkpoints(tmp_path: Path):
    epw = make_epw(tmp_path / "source.epw")
    ws = ProjectWorkspace.create(
        root=tmp_path / "project", project_name="Singapore", city_name="Singapore", baseline_source=epw,
        scenarios=["ssp126"], periods=["2040"], gcms=["ACCESS-CM2"],
    )
    ws.cmip6_status_file.write_text(json.dumps({
        "total": 200,
        "cached": 12,
        "complete_assets": 12,
        "city_cached_within_pending_assets": 5,
        "cities": ["Singapore"],
        "locations": [{"city": "Singapore", "latitude": ws.latitude, "longitude": ws.longitude}],
    }), encoding="utf-8")

    snap = ws.status_snapshot()
    assert snap.cmip6_complete == 12
    assert snap.city_cached == 5
    assert snap.remote_ready == 17
    assert snap.cmip6_missing == 188
