# Future EPW Generator v0.9.1 UX / State Design

## Goal

Improve the v0.9 Functional MVP without changing the scientific engine. v0.9.1 fixes CMIP6 progress semantics, adds ETA, reopens the last project automatically, and introduces a persistent Settings UI with bilingual English/Chinese text and adjustable font size.

## Non-goals

- Do not change Stage 00–05 scientific algorithms.
- Do not change the Protocol R1 SSP/GCM/variable matrix.
- Do not alter cache scientific contents or provenance semantics.
- Do not add automatic baseline EPW discovery, batch-city workflows, accounts, cloud execution, or maps.
- Do not redesign the full visual style.

## 1. CMIP6 progress semantics

The GUI must distinguish three quantities:

1. **Asset cache complete** — authoritative main progress. Count only fully assembled Stage-02 asset cache outputs. This is the only value used for the main `x / 200` progress and percentage.
2. **City checkpoints ready** — internal resumability telemetry. Count city-level extracted checkpoints separately; never add them to completed assets.
3. **Remote data ready** — optional secondary telemetry indicating items that do not require another city extraction because either a full asset or resumable checkpoint already exists.

The main progress must never move backward merely because the app is resumed. All CMIP6 page locations (header percentage, cache card, footer/status bar) must use the same authoritative completed-asset count.

## 2. ETA / throughput

ETA is informative only and must be labelled as an estimate.

- Record elapsed time for genuine remote extraction completions during the current run.
- Ignore cache hits and already-existing checkpoints when calculating remote extraction speed.
- Before at least 3 valid timing samples exist, display `Estimating…` / `正在估算…`.
- After 3 samples, calculate a robust rolling estimate from the most recent 8 genuine remote extraction durations. Use the median of the sample window to reduce outlier impact.
- Remaining work for ETA is based on items that still require remote extraction, not simply `200 - completed_asset_count`.
- Display estimated remaining duration in human-readable units and current typical seconds per remote asset.
- Reset the timing window when the provider changes (GCS to AWS or AWS to GCS), because provider performance can differ materially.
- Pausing freezes the current ETA display; resuming rebuilds the estimate from new run samples.

## 3. Recent project reopening

Application-level settings store the last successfully opened/saved project path.

Default behavior:
- `Reopen last project automatically = true`.
- On startup, if the setting is enabled and the path still contains a valid `project.json`, open it automatically.
- If the path is missing or invalid, start in new-project mode without raising a blocking error.
- Opening a project updates the last-project path.
- Creating/saving a project updates the last-project path.

This setting is application-level and must not be written into research project provenance.

## 4. Settings subsystem

Create an application settings service independent of project workspaces.

Persistent fields:
- `language`: `en` or `zh_CN`; default `en`.
- `text_scale`: `small`, `standard`, or `large`; default `standard`.
- `reopen_last_project`: boolean; default `true`.
- `show_detailed_log`: boolean; default `false`.
- `last_project_path`: string or null.

Settings must be persisted atomically in the user's normal application configuration directory. Corrupt settings must fall back to defaults rather than preventing startup.

## 5. Settings UI

Add a gear/settings control at the top-right of the main window, separate from the left research-workflow navigation.

The settings dialog contains:

### General
- Language: `English` / `简体中文`
- Text size: `Small` / `Standard` / `Large`
- Startup: `Reopen last project automatically`

### Display
- `Show detailed backend log by default`

### Actions
- `Restore defaults`
- `Cancel`
- `Apply`

Language and text size changes apply immediately after `Apply`, without application restart.

## 6. Internationalization

Use a central lightweight i18n dictionary rather than per-page hardcoded language branches.

Requirements:
- Cover the complete user-facing UI: Project, Climate, CMIP6, Generate, Validation, Settings, navigation labels, buttons, status text, dialogs, preflight labels, error messages, and normal workflow guidance.
- Keep scientific identifiers unchanged where translation would reduce clarity: CMIP6, SSP1-2.6, SSP2-4.5, SSP3-7.0, GCS, AWS, BTWS, BWS, `tas`, `huss`, `rsds`, etc.
- Missing keys must safely fall back to English.
- Translation keys are stable semantic identifiers, not source English strings.

## 7. Text scaling

Implement application-wide text scaling with three presets:
- `small`: 0.90
- `standard`: 1.00
- `large`: 1.15

Scaling applies to user-facing text while preserving the established layout hierarchy. It must not alter scientific values or project data.

## 8. State boundaries

Keep three state domains separate:

1. **Research project state**: project.json, workflow_state.json, cache, outputs, provenance.
2. **Runtime CMIP6 telemetry**: current provider, current asset, ETA timing samples, running/paused state.
3. **Application preferences**: language, text size, reopen-last-project, log visibility, last project path.

No application preference may change scientific output.

## 9. Tests / acceptance

v0.9.1 is accepted when all of the following pass:

1. With 12 complete assets and 12 city checkpoints, the main GUI shows `12 / 200`, not `24 / 200`.
2. Header percentage, scientific-cache card and footer show the same completed-asset count.
3. Resume continues from the correct scientific cache and does not reset completed assets.
4. ETA shows `Estimating…` before 3 genuine remote timing samples.
5. ETA uses only genuine remote extraction samples and resets its timing window after provider changes.
6. A saved project is automatically reopened on next startup when enabled.
7. Disabling auto-reopen starts in new-project mode on the next launch.
8. Switching to Chinese updates the whole user-facing UI without changing research project files.
9. Switching back to English restores English UI.
10. Small/standard/large text scale applies globally and persists across restarts.
11. Corrupt/missing settings file falls back to defaults without blocking app startup.
12. Existing v0.9 project workspaces open successfully without migration.
13. All existing application tests and scientific engine tests still pass.

## Version

Display version label: `v0.9.1 • Functional MVP`.
