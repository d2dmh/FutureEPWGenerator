# Future EPW Generator v0.9.2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Make Advanced Mode drive the real Stage 01–05 subset and add a searchable, cached baseline-weather library while preserving full Protocol R1 reproducibility.

**Architecture:** Persist one `climate_selection` object in `project.json`, generate a filtered project manifest from the frozen catalog, and make every downstream count/selector derive from that selection. Add a separate application-level weather catalog/cache service; selected EPWs are validated then copied into project-local inputs so projects stay self-contained.

**Tech Stack:** Python 3, PySide6, pandas, stdlib urllib/zipfile/json/hashlib, existing engine_core.

**Spec:** `docs/superpowers/specs/2026-09-15-future-epw-generator-v0.9.2-design.md`

## Global Constraints

- Preserve BTWS/BWS equations, variable transformations, historical window 1985–2014, validated 5 GCMs, and SSP126/245/370.
- Reproducible mode remains 200 Stage-02 assets and 36 EPWs.
- Advanced mode total = GCM × (1 + SSP) × 10; periods do not multiply remote assets.
- Do not delete compatible old cache when selection changes.
- Baseline library metadata is bundled; EPW binaries are downloaded on demand and validated before use.
- Local EPW browsing remains supported.

---

### Task 1: Climate selection persistence and dynamic counts
**Files:** Modify `future_epw_demo/demo_state.py`, `future_epw_demo/project_workspace.py`, `future_epw_demo/pages/climate_page.py`; Test `tests/test_dynamic_selection.py`.
**Interfaces:** Produce `ProjectWorkspace.mode`, `dynamic_asset_total()`, `selection_fingerprint()`, and persisted `climate_selection`.
- [x] Write failing tests for 1 GCM + 1 SSP = 20 assets and 2 expected EPWs for one period.
- [x] Persist/load selection with v0.9.1 compatibility defaulting to reproducible mode.
- [x] Make Advanced Mode editable, enforce non-empty selections, and save mode/selection.
- [x] Run targeted tests.

### Task 2: Dynamic Stage 01 project manifest
**Files:** Modify `engine_core/src/catalog.py`, `engine_core/src/workflow.py`, `engine_core/01_prepare_manifest.py`, `future_epw_demo/backend.py`; Test `engine_core/tests/test_catalog_workflow.py`, `tests/test_dynamic_selection.py`.
**Interfaces:** Stage 01 accepts `--models`, `--experiments`, `--periods`; manifest metadata records fingerprint and expected asset count.
- [x] Add failing engine tests for a 20-row custom manifest.
- [x] Filter the frozen catalog using selected validated models/experiments.
- [x] Build case matrix from selected models/scenarios/periods.
- [x] Pass selection from GUI backend command.
- [x] Run targeted tests.

### Task 3: Dynamic Stage 03–05 execution
**Files:** Modify `engine_core/src/factors.py`, `engine_core/03_build_climate_factors.py`, `future_epw_demo/backend.py`, `future_epw_demo/project_workspace.py`, `future_epw_demo/preflight.py`; Test engine factor/CLI tests and app preflight tests.
**Interfaces:** `build_factors(..., models, scenarios, target_labels)` only requires selected combinations; Stage 04 selectors already derive from workspace; validation count derives from generation outputs.
- [x] Add failing factor test for one model/one SSP/one period.
- [x] Parameterize factor construction and CLI selectors.
- [x] Replace hard-coded 200/36 assumptions with workspace dynamic totals.
- [x] Ensure selection changes invalidate stale manifest/factors/output state without deleting reusable cache.
- [x] Run targeted tests.

### Task 4: Dynamic CMIP6 progress and ETA
**Files:** Modify `future_epw_demo/project_workspace.py`, `future_epw_demo/workflow_state.py`, `future_epw_demo/pages/cmip6_page.py`; Test `tests/test_workflow_state.py`, `tests/test_dynamic_selection.py`.
**Interfaces:** Main denominator always `ws.dynamic_asset_total()` or current project manifest rows.
- [x] Add tests for 2/20 progress and remote-ready semantics.
- [x] Make status snapshot filter/count only keys belonging to the current dynamic manifest.
- [x] Update CMIP6 labels/ETA denominator from dynamic total.
- [x] Run targeted tests.

### Task 5: Weather catalog and cache service
**Files:** Create `assets/weather_catalog.json`, `future_epw_demo/weather_library.py`; Test `tests/test_weather_library.py`.
**Interfaces:** `WeatherCatalog.search(query)`, `WeatherLibrary.cached_epw(record)`, `download_and_validate(record)`.
- [x] Add catalog schema/search tests including Tokyo/Singapore/London and at least 40 records.
- [x] Implement application-data cache paths, archive download, safe ZIP extraction, preferred EPW resolution, 8760/WMO/coordinate validation.
- [x] Ensure cached EPW can be reused offline.
- [x] Run targeted tests.

### Task 6: Project-page Weather Library UI and city/station separation
**Files:** Modify `future_epw_demo/pages/project_page.py`, `future_epw_demo/project_workspace.py`, `future_epw_demo/i18n.py`; Test `tests/test_ui_workflow_contract.py`, `tests/test_project_safety.py`.
**Interfaces:** Library selection sets canonical city while EPW metadata preserves station; local EPW fallback no longer leaves stale summary city.
- [x] Add source-contract tests for Weather Library controls and city/station separation.
- [x] Add searchable combo/list and Download & Use / Use Cached actions.
- [x] Synchronize summary city whenever EPW or library selection changes.
- [x] Add English/Chinese strings.
- [x] Run targeted tests.

### Task 7: Compatibility, stale-output handling, and provenance
**Files:** Modify `future_epw_demo/project_workspace.py`, `future_epw_demo/preflight.py`, `engine_core/01_prepare_manifest.py`, release docs; Tests across project/preflight/backend.
**Interfaces:** Old v0.9.1 projects load as reproducible; manifest fingerprint mismatch blocks Generate; compatible cache is reused.
- [x] Add compatibility and stale-selection tests.
- [x] Record mode/models/SSPs/periods/asset total in manifest metadata/project provenance.
- [x] Reconcile workflow state against current selection.
- [x] Run app regression.

### Task 8: Full verification and release package
**Files:** Update `VERSION`, `README.md`, `CHANGELOG.md`, `RELEASE_NOTES_v0.9.2.md`, acceptance checklist.
- [x] Run application tests from repo root excluding engine tests.
- [x] Run self-test and compileall.
- [x] Run engine tests from `engine_core` working directory.
- [x] Remove caches and package full v0.9.2 ZIP.
- [x] Extract ZIP and rerun self-test/application tests from the packaged tree.
