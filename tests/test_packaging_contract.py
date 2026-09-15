from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(rel):
    return (ROOT / rel).read_text(encoding='utf-8')

def test_pyinstaller_spec_contract():
    spec = read('packaging/FutureEPWGenerator.spec')
    assert 'FutureEPWGenerator' in spec
    assert 'FutureEPWEngine' in spec
    assert 'app_icon.ico' in spec
    assert 'engine_core' in spec
    assert 'weather_catalog.json' in spec
    assert 'windows_version_info.txt' in spec
    assert 'COLLECT(' in spec

def test_inno_setup_contract():
    iss = read('packaging/FutureEPWGenerator.iss')
    assert 'AppVersion=1.0.0' in iss
    assert 'FutureEPWGenerator_Setup_v1.0.0' in iss
    assert 'FutureEPWGenerator.exe' in iss
    assert '[Icons]' in iss
    assert 'UninstallDisplayIcon' in iss

def test_windows_build_scripts_exist():
    for rel in ['scripts/build_windows.ps1','scripts/build_installer.ps1']:
        assert (ROOT / rel).is_file()

def test_windows_release_workflow_contract():
    yml = read('.github/workflows/windows-release.yml')
    assert 'windows-latest' in yml
    assert 'python-version: "3.11"' in yml or "python-version: '3.11'" in yml
    assert 'build_windows.ps1' in yml
    assert 'build_installer.ps1' in yml
    assert 'FutureEPWGenerator_Setup_v1.0.0.exe' in yml


def test_pyinstaller_spec_resolves_project_root_from_spec_directory():
    spec = read('packaging/FutureEPWGenerator.spec')
    assert 'project_root = Path(SPECPATH).resolve().parent\n' in spec
    assert 'Path(SPECPATH).resolve().parent.parent' not in spec


def test_windows_build_stops_on_native_command_failure():
    ps1 = read('scripts/build_windows.ps1')
    assert 'Application tests failed with exit code $LASTEXITCODE' in ps1
    assert 'PyInstaller failed with exit code $LASTEXITCODE' in ps1


def test_pyinstaller_spec_collects_conda_expat_runtime():
    spec = read('packaging/FutureEPWGenerator.spec')
    assert 'Library' in spec and 'bin' in spec
    assert '*expat*.dll' in spec
    assert 'sys.prefix' in spec


def test_windows_build_checks_bundled_expat_before_frozen_self_test():
    ps1 = read('scripts/build_windows.ps1')
    assert '*expat*.dll' in ps1
    assert 'Bundled Expat runtime DLL missing' in ps1
