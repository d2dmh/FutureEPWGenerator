# Changelog

## v1.0.0
- Added self-contained Windows release engineering using PyInstaller onedir + Inno Setup.
- Added separate `FutureEPWGenerator.exe` GUI and `FutureEPWEngine.exe` console backend runner so frozen Stage 00–05 logs and worker subprocesses remain reliable.
- Added frozen resource resolution for `assets/`, `engine_core/`, Weather Library catalog and `VERSION`.
- Added first-launch bilingual welcome dialog and formal `Version 1.0.0 · Protocol R1` product identity.
- Added LocalAppData Weather Library cache on Windows while keeping application settings outside research projects.
- Added Windows PowerShell build scripts and GitHub Actions release automation for tag `v1.0.0`.
- Added Inno Setup per-user installer, Start Menu shortcut, optional desktop shortcut and uninstall support.
- Scientific Stage 00–05 algorithms remain unchanged from the validated v0.9.2.1 baseline; only frozen-process orchestration was adapted for packaging.

## v0.9.2.1-functional-mvp
- Replaced the editable Weather Library combo box with a bounded search + result-list selector to prevent overlap under Chinese/large-text layouts.
- Made the Project page scrollable for robust small-window and large-text operation.
- Added an explicit read-only Station field beside the canonical City field.
- Added display-city recovery for older projects that stored the EPW station name as `city`, without changing their persisted cache/location identity.
- Preserved v0.9.2 dynamic CMIP6 selection and all Stage 00–05 scientific algorithms.

## v0.9.2-functional-mvp
- Added true Advanced Mode execution: selected validated GCM/SSP/period subsets now drive Stage 01–05, CMIP6 totals, ETA, preflight and expected output counts.
- Added selection-specific Stage-01 manifest metadata and fingerprints.
- Added dynamic Stage-03 factor generation and Stage-04 output generation for the selected subset; one-GCM selections still emit a separate ensemble-mean artifact for consistent structure.
- Replaced fixed 200-asset completion gates with active-manifest totals while keeping Reproducible Mode at 200 assets / 36 EPWs.
- Added a bundled 40-city Baseline Weather Library catalog with searchable city/station/WMO lookup, on-demand download, global caching, ZIP/EPW/WMO/coordinate validation and project-local baseline copying.
- Separated canonical project city from EPW station name; known catalog WMO stations can supply the canonical city for local EPWs.
- Added localized Weather Library errors and persisted baseline-library provenance.
- Preserved compatible CMIP6 cache on climate-selection changes and archives stale derived outputs under `outputs/stale/<selection-fingerprint>/`.
- Preserved the validated morphing equations and Protocol R1 historical/model/scenario definitions.

## v0.9.1-functional-mvp
- Fixed Stage-02 progress semantics: complete asset cache, city checkpoints, and remote-ready work are now separate quantities.
- Added filesystem-authoritative reconciliation so stale v0.9 status JSON cannot inflate completed-asset progress.
- Added CMIP6 ETA using the median of the latest 8 genuine remote extraction timings after at least 3 samples; cache hits are excluded and provider changes reset the timing window.
- Added persistent application Settings independent of research project provenance.
- Added English / Simplified Chinese UI switching without application restart.
- Added Small / Standard / Large global text scaling (0.90 / 1.00 / 1.15).
- Added automatic reopening of the last valid project, enabled by default.
- Added a detailed-log default preference.
- Localized navigation, pages, normal workflow guidance, preflight failures and common user-facing errors while keeping scientific identifiers unchanged.
- Preserved all Protocol R1 Stage 00–05 scientific algorithms and command-line engine behavior.

## v0.9.0-functional-mvp
- Added safe Create/Open project separation; existing projects and non-empty unrelated folders are no longer silently overwritten.
- Added baseline EPW SHA-256 identity and metadata persistence; later baseline replacement is detected and generation is blocked.
- Added `runtime/workflow_state.json` with atomic persistence and restart reconciliation from real artifacts.
- Added strict Stage 03, Stage 04 and Stage 05 completion helpers so process exit code alone cannot mark a project complete.
- Added an eight-check blocking generation preflight covering project, baseline, location, Protocol R1, manifest, 200/200 cache, writable output and workflow-idle state.
- Added persistent CMIP6 Resume/Pause/Retry Failed behavior while preserving the existing Stage-02 cache and pause semantics.
- Added structured subprocess failure context with recent output and log path while retaining merged QProcess output.
- Updated validation and navigation to show `PASS`, `PASS WITH WARNINGS`, or `FAIL` from reconciled project truth.
- Preserved the frozen Protocol R1 scientific commands, scenarios, periods, GCMs, variables, bilinear extraction, GCS→AWS fallback and morphing methods.

## v0.8.0-arbitrary-city-alpha
- Removed the eight-WMO project creation restriction.
- Added editable target city labels.
- Added EPW-coordinate mode and explicit manual target-coordinate mode.
- Added `runtime/location_spec.json` provenance shared by Stage 00, Stage 02 and Stage 04.
- Added location-namespaced CMIP6 caches so another city's cache cannot create a false `200/200` status.
- Added current-location status fields (`current_city_complete` / `current_city_total`).
- Added read-only migration/seeding from legacy v0.7/v1.5 multi-city caches for compatible original stations.
- Preserved the Protocol R1 climate models, variables, scenarios, windows, bilinear interpolation, GCS→AWS fallback and v1.5.1 precipitation fallback.

## v0.7.0-functional-alpha
- Kept v0.5 UI as the visual baseline.
- Connected real project workspaces and EPW metadata parsing.
- Bundled validated CMIP6 workflow engine v1.5.1.
- Added real Stage 00–05 subprocess orchestration.
