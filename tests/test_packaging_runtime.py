from __future__ import annotations

import sys
from pathlib import Path


def test_bundle_root_uses_source_tree_when_not_frozen(monkeypatch):
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    monkeypatch.delattr(sys, "frozen", raising=False)
    from future_epw_demo.runtime_paths import bundle_root
    assert (bundle_root() / "app.py").is_file()


def test_bundle_root_uses_meipass_when_frozen(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    from future_epw_demo.runtime_paths import bundle_root
    assert bundle_root() == tmp_path.resolve()


def test_backend_builds_frozen_stage_command(monkeypatch, tmp_path: Path):
    from future_epw_demo.backend import WorkflowBackend
    engine = tmp_path / "engine_core"
    engine.mkdir()
    (engine / "00_check_environment.py").write_text("print('ok')\n", encoding="utf-8")
    backend = WorkflowBackend(engine_dir=engine, python_executable="FutureEPWGenerator.exe", frozen_mode=True)
    command = backend._stage_command("00_check_environment.py", "--help")
    assert command[:3] == ["FutureEPWGenerator.exe", "--engine-stage", "00_check_environment.py"]
    assert command[-1] == "--help"


def test_backend_builds_source_stage_command(tmp_path: Path):
    from future_epw_demo.backend import WorkflowBackend
    engine = tmp_path / "engine_core"
    engine.mkdir()
    script = engine / "00_check_environment.py"
    script.write_text("print('ok')\n", encoding="utf-8")
    backend = WorkflowBackend(engine_dir=engine, python_executable="python", frozen_mode=False)
    command = backend._stage_command("00_check_environment.py", "--help")
    assert command == ["python", str(script), "--help"]


def test_app_engine_stage_dispatch_help_runs_without_gui():
    import subprocess
    result = subprocess.run(
        [sys.executable, "app.py", "--engine-stage", "01_prepare_manifest.py", "--help"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "usage:" in (result.stdout + result.stderr).lower()


def test_frozen_engine_executable_is_sibling_console_runner(monkeypatch):
    import future_epw_demo.runtime_paths as rp
    monkeypatch.setattr(rp.sys, "frozen", True, raising=False)
    monkeypatch.setattr(rp.sys, "executable", "/opt/FutureEPWGenerator/FutureEPWGenerator.exe", raising=False)
    assert rp.frozen_engine_executable().name == "FutureEPWEngine.exe"
    assert rp.frozen_engine_executable().parent.name == "FutureEPWGenerator"
