from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import json
import os
from pathlib import Path
import sys

VALID_LANGUAGES = {"en", "zh_CN"}
VALID_TEXT_SCALES = {"small", "standard", "large"}


@dataclass(frozen=True)
class AppSettings:
    language: str = "en"
    text_scale: str = "standard"
    reopen_last_project: bool = True
    show_detailed_log: bool = False
    last_project_path: str | None = None
    welcome_seen: bool = False


def default_settings_path() -> Path:
    override = os.environ.get("FUTURE_EPW_SETTINGS_PATH")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
    return base / "FutureEPWGenerator" / "settings.json"


def reopen_candidate(settings: AppSettings) -> Path | None:
    """Return the last project root only when automatic reopen is enabled and valid."""
    if not settings.reopen_last_project or not settings.last_project_path:
        return None
    root = Path(settings.last_project_path).expanduser().resolve()
    return root if (root / "project.json").is_file() else None


class AppSettingsStore:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path).expanduser() if path is not None else default_settings_path()

    @staticmethod
    def _sanitize(payload: dict) -> AppSettings:
        defaults = AppSettings()
        language = payload.get("language", defaults.language)
        if language not in VALID_LANGUAGES:
            language = defaults.language
        text_scale = payload.get("text_scale", defaults.text_scale)
        if text_scale not in VALID_TEXT_SCALES:
            text_scale = defaults.text_scale
        reopen = payload.get("reopen_last_project", defaults.reopen_last_project)
        show_log = payload.get("show_detailed_log", defaults.show_detailed_log)
        last_project = payload.get("last_project_path", defaults.last_project_path)
        welcome_seen = payload.get("welcome_seen", defaults.welcome_seen)
        if last_project is not None and not isinstance(last_project, str):
            last_project = None
        return AppSettings(
            language=language,
            text_scale=text_scale,
            reopen_last_project=bool(reopen),
            show_detailed_log=bool(show_log),
            last_project_path=last_project,
            welcome_seen=bool(welcome_seen),
        )

    def load(self) -> AppSettings:
        if not self.path.is_file():
            return AppSettings()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return AppSettings()
            allowed = {f.name for f in fields(AppSettings)}
            return self._sanitize({k: v for k, v in payload.items() if k in allowed})
        except Exception:
            return AppSettings()

    def save(self, settings: AppSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.path)

    def reset(self) -> AppSettings:
        settings = AppSettings()
        self.save(settings)
        return settings
