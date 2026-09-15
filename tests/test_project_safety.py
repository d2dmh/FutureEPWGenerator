from pathlib import Path
import json
import pytest

from future_epw_demo.errors import ProjectConflictError, BaselineFingerprintMismatchError
from future_epw_demo.project_workspace import ProjectWorkspace
from tests.test_functional_backend import make_epw

DEFAULTS = dict(
    scenarios=["ssp126", "ssp245", "ssp370"],
    periods=["2040", "2060"],
    gcms=["ACCESS-CM2", "GFDL-ESM4", "MPI-ESM1-2-HR", "IPSL-CM6A-LR", "FGOALS-g3"],
)


def test_create_rejects_existing_future_epw_project(tmp_path: Path):
    epw = make_epw(tmp_path / "source.epw")
    root = tmp_path / "project"
    ProjectWorkspace.create(root=root, project_name="A", baseline_source=epw, **DEFAULTS)
    with pytest.raises(ProjectConflictError):
        ProjectWorkspace.create(root=root, project_name="B", baseline_source=epw, **DEFAULTS)


def test_create_rejects_nonempty_unrelated_directory(tmp_path: Path):
    epw = make_epw(tmp_path / "source.epw")
    root = tmp_path / "occupied"
    root.mkdir()
    (root / "notes.txt").write_text("do not overwrite", encoding="utf-8")
    with pytest.raises(ProjectConflictError):
        ProjectWorkspace.create(root=root, project_name="A", baseline_source=epw, **DEFAULTS)


def test_project_json_stores_baseline_sha256_and_metadata(tmp_path: Path):
    epw = make_epw(tmp_path / "source.epw")
    ws = ProjectWorkspace.create(root=tmp_path / "project", project_name="A", baseline_source=epw, **DEFAULTS)
    payload = json.loads(ws.project_file.read_text(encoding="utf-8"))
    assert payload["baseline"]["sha256"] == ws.baseline_sha256()
    assert payload["baseline"]["hours"] == 8760
    assert payload["baseline"]["relative_path"].startswith("inputs/baseline_epw/")


def test_baseline_replacement_is_detected(tmp_path: Path):
    epw = make_epw(tmp_path / "source.epw")
    ws = ProjectWorkspace.create(root=tmp_path / "project", project_name="A", baseline_source=epw, **DEFAULTS)
    ws.baseline_path.write_text(ws.baseline_path.read_text(encoding="utf-8") + "# changed\n", encoding="utf-8")
    with pytest.raises(BaselineFingerprintMismatchError):
        ws.assert_baseline_integrity()


def test_save_does_not_bless_a_replaced_baseline(tmp_path: Path):
    epw = make_epw(tmp_path / "source.epw")
    ws = ProjectWorkspace.create(root=tmp_path / "project", project_name="A", baseline_source=epw, **DEFAULTS)
    original = json.loads(ws.project_file.read_text(encoding="utf-8"))["baseline"]["sha256"]
    ws.baseline_path.write_text(ws.baseline_path.read_text(encoding="utf-8") + "# changed\n", encoding="utf-8")
    ws.project_name = "Renamed"
    ws.save()
    payload = json.loads(ws.project_file.read_text(encoding="utf-8"))
    assert payload["baseline"]["sha256"] == original
    assert ws.verify_baseline_fingerprint() is False


def test_portable_project_relative_path_uses_forward_slashes():
    import future_epw_demo.project_workspace as project_workspace
    assert project_workspace._portable_relative_path('inputs', 'baseline_epw', 'source.epw') == 'inputs/baseline_epw/source.epw'
