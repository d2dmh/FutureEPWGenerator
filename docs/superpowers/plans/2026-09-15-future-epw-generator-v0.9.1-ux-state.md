# Future EPW Generator v0.9.1 UX / State Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix Stage-02 progress semantics, add robust ETA, persistent application settings, automatic last-project reopen, bilingual English/Chinese UI, and global text scaling without changing the Stage 00–05 scientific engine.

**Architecture:** Keep research project state, transient CMIP6 telemetry, and application preferences separate. Add pure-Python `app_settings.py`, `i18n.py`, and `eta.py` services, then wire them into the existing PySide6 shell/pages. CMIP6 main progress will be computed only from complete asset CSVs; city checkpoints remain secondary telemetry.

**Tech Stack:** Python 3.11+, PySide6, stdlib JSON/pathlib/statistics, pytest.

**Spec:** `docs/superpowers/specs/2026-09-15-future-epw-generator-v0.9.1-ux-state-design.md`

## Global Constraints

- Do not change Stage 00–05 scientific algorithms.
- Keep Protocol R1 scenario/GCM/variable matrix unchanged.
- Preserve existing v0.9 project compatibility.
- Application settings must not be written to research project provenance.
- UI language and text-scale changes must not change scientific outputs.
- Main Stage-02 progress is complete asset cache only; checkpoints are never added to completed assets.
- ETA uses the median of the latest 8 genuine remote extraction durations and requires 3 valid samples.
- Display version `v0.9.1 • Functional MVP`.

---

### Task 1: Correct Stage-02 progress semantics

**Files:**
- Modify: `future_epw_demo/project_workspace.py`
- Modify: `future_epw_demo/demo_state.py`
- Test: `tests/test_functional_backend.py`

**Interfaces:**
- `WorkspaceStatus.cmip6_complete`: count of fully assembled asset cache CSVs only.
- `WorkspaceStatus.city_cached`: count of city checkpoint CSVs only.
- `WorkspaceStatus.remote_ready`: union of completed assets and checkpoint asset keys, capped at total.

- [ ] Add a regression test with 12 complete asset CSVs and 12 city checkpoint CSVs that asserts `cmip6_complete == 12`, `city_cached == 12`, and `remote_ready == 12` when checkpoint names correspond to the same 12 assets.
- [ ] Add a regression test for status JSON where `cached=12` and `city_cached_within_pending_assets=5`; assert main progress remains 12 and remote-ready becomes 17.
- [ ] Implement the separate counts and union semantics in `status_snapshot()`.
- [ ] Run `python -m pytest -q tests/test_functional_backend.py tests/test_workflow_state.py tests/test_preflight.py`.

### Task 2: Add application settings service

**Files:**
- Create: `future_epw_demo/app_settings.py`
- Test: `tests/test_app_settings.py`

**Interfaces:**
- `AppSettings(language='en', text_scale='standard', reopen_last_project=True, show_detailed_log=False, last_project_path=None)`
- `AppSettingsStore(path: Path | None = None).load() -> AppSettings`
- `AppSettingsStore.save(settings: AppSettings) -> None`
- `AppSettingsStore.reset() -> AppSettings`

- [ ] Write tests for defaults, atomic persistence, corrupt JSON fallback, and invalid enum fallback.
- [ ] Implement OS-appropriate config path with `FUTURE_EPW_SETTINGS_PATH` override for tests.
- [ ] Persist JSON atomically through `.tmp` replacement.
- [ ] Run `python -m pytest -q tests/test_app_settings.py`.

### Task 3: Add i18n and text scaling primitives

**Files:**
- Create: `future_epw_demo/i18n.py`
- Modify: `future_epw_demo/theme.py`
- Test: `tests/test_i18n.py`

**Interfaces:**
- `Translator(language='en').text(key, **kwargs) -> str`
- `Translator.set_language(language) -> None`
- `scaled_app_style(scale_name: str) -> str`

- [ ] Test English/Chinese translation, missing-key English fallback, and parameter formatting.
- [ ] Test style scaling maps small/standard/large to 0.90/1.00/1.15 and modifies stylesheet font-size declarations.
- [ ] Implement stable semantic keys for global shell, workflow status, Project/Climate/CMIP6/Generate/Validation/Settings UI strings.
- [ ] Run `python -m pytest -q tests/test_i18n.py`.

### Task 4: Add robust CMIP6 ETA telemetry

**Files:**
- Create: `future_epw_demo/eta.py`
- Modify: `future_epw_demo/pages/cmip6_page.py`
- Test: `tests/test_eta.py`

**Interfaces:**
- `ExtractionETA.start_asset(asset_id, provider, started_at=None)`
- `ExtractionETA.finish_asset(asset_id, provider, finished_at=None, genuine_remote=True)`
- `ExtractionETA.change_provider(provider)` resets samples on provider change.
- `ExtractionETA.estimate(remaining_remote: int) -> ETAEstimate`

- [ ] Test no estimate before 3 genuine samples, median of latest 8, cache-hit exclusion, provider reset, pause/freeze behavior, and human duration formatting.
- [ ] Parse Stage-02 extraction lines to start timers and `asset complete` lines to finish genuine remote timers.
- [ ] Feed remaining work from `WorkspaceStatus.remote_ready`, not `200-complete`.
- [ ] Add visible ETA, typical seconds/asset, completed-assets, checkpoints, and remote-ready telemetry to CMIP6 page.
- [ ] Make header percentage/cache card/footer all use authoritative complete asset count.
- [ ] Run `python -m pytest -q tests/test_eta.py tests/test_functional_backend.py tests/test_ui_workflow_contract.py`.

### Task 5: Add Settings dialog and last-project reopen

**Files:**
- Create: `future_epw_demo/settings_dialog.py`
- Modify: `future_epw_demo/main_window.py`
- Modify: `future_epw_demo/pages/project_page.py`
- Modify: `app.py`
- Test: `tests/test_source_contract.py`
- Test: `tests/test_ui_workflow_contract.py`

**Interfaces:**
- `SettingsDialog(settings, translator, parent=None)` returns updated settings on Apply.
- `MainWindow(..., settings_store=None)` owns application settings independently of project workspace.
- `MainWindow.try_reopen_last_project()` silently loads a valid last project when enabled.

- [ ] Add source-contract tests for gear control, settings fields, version label, last-project setting updates, and startup reopen call.
- [ ] Add Settings dialog with General/Display groups and Apply/Cancel/Restore Defaults.
- [ ] Update last-project path after successful create/open.
- [ ] Auto-reopen valid last project on startup; invalid/missing paths fall back to new-project mode without blocking error.
- [ ] Run application source/contract tests.

### Task 6: Wire bilingual retranslation across all pages

**Files:**
- Modify: `future_epw_demo/widgets.py`
- Modify: `future_epw_demo/main_window.py`
- Modify: `future_epw_demo/pages/project_page.py`
- Modify: `future_epw_demo/pages/climate_page.py`
- Modify: `future_epw_demo/pages/cmip6_page.py`
- Modify: `future_epw_demo/pages/generate_page.py`
- Modify: `future_epw_demo/pages/validation_page.py`
- Modify: `future_epw_demo/preflight.py`
- Modify: `future_epw_demo/errors.py`
- Test: `tests/test_i18n.py`
- Test: `tests/test_source_contract.py`

**Interfaces:**
- Each page exposes `retranslate_ui()` and reads from the shared `Translator`.
- Dynamic status rendering uses translation keys while scientific identifiers stay unchanged.

- [ ] Add stable i18n keys to reusable widgets and every page's user-facing static/dynamic text.
- [ ] Preserve CMIP6/SSP/GCS/AWS/BTWS/BWS/tas/etc. identifiers untranslated.
- [ ] Ensure English is default and missing keys fall back safely.
- [ ] Run translation/source contract tests.

### Task 7: Apply persistent text scale and log preference

**Files:**
- Modify: `future_epw_demo/main_window.py`
- Modify: `future_epw_demo/pages/cmip6_page.py`
- Modify: `future_epw_demo/theme.py`
- Test: `tests/test_i18n.py`
- Test: `tests/test_source_contract.py`

**Interfaces:**
- `MainWindow.apply_preferences()` applies stylesheet, translator language, and log visibility.

- [ ] Apply `scaled_app_style()` after Settings Apply and at startup.
- [ ] Set detailed log visibility from `show_detailed_log` and persist changes only through Settings.
- [ ] Verify research project JSON is untouched by preference changes through a pure-Python regression test where possible.
- [ ] Run affected tests.

### Task 8: Documentation, versioning, and full regression

**Files:**
- Modify: `VERSION`
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Create: `RELEASE_NOTES_v0.9.1.md`
- Create: `TEST_RESULTS_v0.9.1.txt`

**Interfaces:** none.

- [ ] Set version to 0.9.1 and document progress semantics, ETA, Settings, Chinese/English, text scale, and auto-reopen.
- [ ] Run `python app.py --self-test`.
- [ ] Run `python -m compileall -q app.py future_epw_demo engine_core`.
- [ ] Run `python -m pytest -q tests`.
- [ ] Run all engine-core test files from `engine_core/`.
- [ ] Package the complete source tree and verify ZIP integrity.
