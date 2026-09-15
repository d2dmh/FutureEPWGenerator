from __future__ import annotations

import json
from pathlib import Path

from future_epw_demo.app_settings import AppSettings, AppSettingsStore


def test_settings_defaults_when_file_missing(tmp_path: Path):
    store = AppSettingsStore(tmp_path / "settings.json")
    assert store.load() == AppSettings()


def test_settings_round_trip_and_atomic_write(tmp_path: Path):
    path = tmp_path / "settings.json"
    store = AppSettingsStore(path)
    settings = AppSettings(
        language="zh_CN",
        text_scale="large",
        reopen_last_project=False,
        show_detailed_log=True,
        last_project_path=r"C:\FutureEPW\Paris",
    )
    store.save(settings)
    assert store.load() == settings
    assert path.is_file()
    assert not path.with_suffix(path.suffix + ".tmp").exists()


def test_corrupt_settings_fall_back_to_defaults(tmp_path: Path):
    path = tmp_path / "settings.json"
    path.write_text("{not-json", encoding="utf-8")
    assert AppSettingsStore(path).load() == AppSettings()


def test_invalid_enum_values_are_sanitized_but_valid_fields_survive(tmp_path: Path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({
        "language": "xx",
        "text_scale": "gigantic",
        "reopen_last_project": False,
        "show_detailed_log": True,
        "last_project_path": "/tmp/project",
    }), encoding="utf-8")
    loaded = AppSettingsStore(path).load()
    assert loaded.language == "en"
    assert loaded.text_scale == "standard"
    assert loaded.reopen_last_project is False
    assert loaded.show_detailed_log is True
    assert loaded.last_project_path == "/tmp/project"


def test_reset_persists_defaults(tmp_path: Path):
    store = AppSettingsStore(tmp_path / "settings.json")
    store.save(AppSettings(language="zh_CN", text_scale="small"))
    reset = store.reset()
    assert reset == AppSettings()
    assert store.load() == AppSettings()


def test_saving_application_preferences_does_not_touch_research_project_file(tmp_path: Path):
    project_file = tmp_path / "project" / "project.json"
    project_file.parent.mkdir(parents=True)
    original = '{"workflow_protocol":"R1","scientific_value":42}\n'
    project_file.write_text(original, encoding="utf-8")

    store = AppSettingsStore(tmp_path / "config" / "settings.json")
    store.save(AppSettings(language="zh_CN", text_scale="large", last_project_path=str(project_file.parent)))

    assert project_file.read_text(encoding="utf-8") == original
    assert store.path.parent != project_file.parent


def test_reopen_candidate_requires_enabled_setting_and_valid_project_json(tmp_path: Path):
    from future_epw_demo.app_settings import reopen_candidate

    root = tmp_path / "project"
    root.mkdir()
    enabled = AppSettings(reopen_last_project=True, last_project_path=str(root))
    assert reopen_candidate(enabled) is None

    (root / "project.json").write_text("{}", encoding="utf-8")
    assert reopen_candidate(enabled) == root.resolve()

    disabled = AppSettings(reopen_last_project=False, last_project_path=str(root))
    assert reopen_candidate(disabled) is None
    missing = AppSettings(reopen_last_project=True, last_project_path=str(tmp_path / "missing"))
    assert reopen_candidate(missing) is None


def test_v1_settings_default_welcome_is_unseen(tmp_path: Path):
    store = AppSettingsStore(tmp_path / "settings.json")
    assert store.load().welcome_seen is False
    store.save(AppSettings(welcome_seen=True))
    assert store.load().welcome_seen is True
