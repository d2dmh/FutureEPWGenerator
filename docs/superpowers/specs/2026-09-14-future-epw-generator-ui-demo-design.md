# Future EPW Generator — UI Demo Design Spec v0.1

Date: 2026-09-14
Status: Approved; v0.1 source implemented. Interactive GUI runtime remains to be verified on a machine with PySide6 installed.
Target: Windows desktop clickable UI demo (mock data only)
Tech: Python + PySide6

## 1. Goal

Build a clickable Windows desktop UI demo for a reproducible CMIP6-based future EPW workflow. The demo validates information architecture and interaction flow before connecting the already validated scientific backend.

The demo does **not** execute real CMIP6 downloads, climate-factor calculations, EPW generation, or validation. All runtime states are simulated with deterministic mock data.

## 2. Product principles

1. Scientific-tool visual style: white background, light-gray cards, restrained blue accents, high information density, minimal decoration.
2. Left navigation doubles as workflow status tracking.
3. GUI controls orchestration and presentation only; scientific algorithms remain independent.
4. Recommended/Reproducible Mode is the default path and protects validated settings from accidental change.
5. Every stage exposes enough provenance and diagnostics for research reproducibility.
6. MVP avoids features that do not directly test the core workflow.

## 3. Main window

### 3.1 Global shell

Persistent layout:

- Top bar
  - App name: `Future EPW Generator`
  - Current project name
  - Optional small status indicator
- Left navigation
  1. Project
  2. Climate
  3. CMIP6
  4. Generate
  5. Validation
- Bottom status bar
  - Cache status
  - Active provider
  - Project state

### 3.2 Navigation status states

Each step supports exactly five visual states:

- `Complete`
- `Running`
- `Warning`
- `Failed`
- `Pending`

The demo must allow these states to update as the user advances through the mocked workflow.

## 4. Page 1 — Project Setup

Purpose: define project identity, baseline EPW, location, and project workspace.

### Required controls

- Project name input
- Project folder input + browse button
- Baseline EPW input + browse button
- Parsed baseline metadata card
  - Station
  - WMO
  - Latitude
  - Longitude
  - Elevation
  - Hour count
  - Valid/invalid status
- Location card
  - City
  - Latitude
  - Longitude
  - `Use coordinates from EPW` checkbox
- `Save Project`
- `Next: Climate`

### Mock behavior

Selecting the demo EPW populates:

- Station: Singapore–Changi Intl AP
- WMO: 486980
- Latitude: 1.36° N
- Longitude: 103.99° E
- Elevation: 16 m
- Hours: 8760
- Status: Valid

When `Use coordinates from EPW` is checked, coordinate fields are read-only.

### Workspace model

The UI should visually communicate that a project will own:

- `project.json`
- `baseline/`
- `cache/`
- `manifest/`
- `factors/`
- `epw/`
- `validation/`
- `logs/`

The demo does not need to create these directories yet.

## 5. Page 2 — Climate Settings

Purpose: configure scenarios, future periods, and climate models with a safe default workflow.

### Mode selector

Default:

- `Recommended / Reproducible Mode`

Optional:

- `Advanced Mode`

### Recommended-mode settings

Scenarios:

- SSP1-2.6
- SSP2-4.5
- SSP3-7.0

Future periods:

- 2040 (2030–2050)
- 2060 (2050–2070)

Climate models:

- ACCESS-CM2
- GFDL-ESM4
- MPI-ESM1-2-HR
- IPSL-CM6A-LR
- FGOALS-g3

Scientific configuration card:

- Historical reference: 1985–2014
- Future windows: 21-year centered climatology
- Spatial interpolation: Bilinear
- Temperature morphing: BTWS
- Solar/cloud: BWS
- Humidity: huss-based
- Pressure: psl
- Wind: sfcWind ratio
- Precipitation: pr ratio + dry-baseline fallback
- Ensemble: 5-model mean

### Output-count logic

The UI calculates expected EPWs dynamically:

`cities × scenarios × periods × (GCMs + ensemble)`

For the single-city demo with all default selections, show 36 EPW.

### Advanced Mode in v0.1

Advanced Mode is a visual placeholder only. It may reveal disabled/read-only advanced fields and a warning that changes can reduce comparability with the validated workflow.

### Configuration fingerprint

Show a read-only identifier such as:

`EPW-R1-1985_2014-SSP126_245_370-2040_2060-5GCM`

## 6. Page 3 — CMIP6 Data

Purpose: communicate long-running Stage 02 progress, provider fallback, cache state, and resumability without exposing raw terminal output by default.

### Main widgets

- Overall progress bar
  - Demo state: 163 / 200
- Current task card
  - Model
  - Scenario
  - Variable
  - City
  - Provider
  - Attempt
  - Status
- Asset summary
  - Complete
  - Pending
  - Failed
  - Cached cities
- Controls
  - Pause
  - Resume
  - Retry Failed
  - Check Status
- Recent activity list
- Collapsible detailed log panel
- Provider status card
  - GCS active / standby / timeout
  - AWS active / standby / fallback
- Disk status
  - Cache size
  - Free disk space

### Mock runtime behavior

`Start/Resume` runs a QTimer-based deterministic simulation:

- Progress increases toward 200
- Current task fields rotate through predefined values
- Recent activity updates
- Provider can simulate a GCS timeout followed by AWS fallback

`Pause` means “stop after current mocked city/task,” then preserve current progress.

`Resume` continues from the preserved progress.

`Check Status` opens a compact dialog summarizing total / complete / missing.

Detailed log is hidden by default and can be expanded.

## 7. Page 4 — Generate EPW

Purpose: show Stage 03 climate-factor construction and Stage 04 EPW generation as two distinct but sequential operations.

### Step 1 — Climate Factors

Show:

- Status: Complete
- Climatology rows: 33,600
- Per-GCM factor rows: 2,880
- Ensemble rows: 2,880
- Precipitation fallback: 6 records
- Warning summary:
  - Kuwait City / IPSL-CM6A-LR / August

Buttons:

- View Climate Factors
- View Warnings

`View Climate Factors` opens a small read-only table with monthly demo factors.

`View Warnings` explains the dry-baseline fallback:

- historical pr near zero
- ratio morphing not applied
- `r_pr = 1.0`
- event recorded in provenance

### Step 2 — EPW Generation

Show:

- Expected outputs
- Generated outputs
- Progress bar
- Current EPW case
- `Generate EPW`
- `Stop after current file`
- Output folder
- `Open folder`

Mock generation uses QTimer and advances to the expected count.

### Preflight checklist

Before mocked generation starts, show all as passed:

- CMIP6 cache complete
- Climate factors complete
- Baseline EPW valid
- Output folder writable
- Disk space sufficient

## 8. Page 5 — Validation & Export

Purpose: translate Stage 05 QA into an immediately understandable scientific validation screen.

### Overall status

Exactly three possible overall states:

- PASSED
- PASSED WITH WARNINGS
- FAILED

The default final demo state is:

`PASSED WITH WARNINGS`

because hard validation passes while six precipitation dry-baseline fallback records remain documented.

### Validation summary

Show:

- File count: 288 / 288 in the 8-city illustrative run summary, or 36 / 36 for the single-city active project
- Hour count: 8760 h each
- Missing values: PASS
- Physical bounds: PASS
- Target vs achieved: PASS
- Audit groups: 2880 / 2880 in the full illustrative run summary

The UI must clearly distinguish the active project count from the previously validated 8-city reference run, to avoid mixing 36 and 288.

### Scientific warnings

Show the six dry-baseline records as a documented warning, not a failure.

### Validation detail table

Columns:

- City
- SSP
- Period
- Model
- Status

Warnings may show as `PASS*` with a details action.

### Output actions

- Open EPW Folder
- Open Validation Report
- Export Project Summary
- Copy Methods Summary

For v0.1 demo, these buttons may show message boxes instead of performing real filesystem actions.

## 9. Visual design system

### Typography

- Chinese: Microsoft YaHei when available
- English/numbers: Arial
- Fallback: system sans-serif

### Color behavior

Use a restrained palette only:

- White background
- Light gray cards/dividers
- Blue primary interaction/accent
- Green success
- Amber warning
- Red failure

No gradients, glassmorphism, heavy shadows, decorative illustrations, or animation beyond progress feedback.

### Spacing

- Desktop-first 16:9-friendly layout
- Left navigation approximately 210–230 px
- Content area should remain readable at 1366×768
- Prefer cards and section headers over dense form grids

## 10. Architecture

Proposed demo structure:

```text
future-epw-generator-demo/
├─ app.py
├─ ui/
│  ├─ main_window.py
│  ├─ project_page.py
│  ├─ climate_page.py
│  ├─ cmip6_page.py
│  ├─ generate_page.py
│  ├─ validation_page.py
│  └─ widgets.py
├─ mock/
│  ├─ demo_data.py
│  └─ workflow_simulator.py
├─ assets/
├─ tests/
└─ README.md
```

### Component boundaries

- `main_window.py`: navigation, global shell, page switching, global state indicators
- page modules: page-specific presentation and local interactions only
- `widgets.py`: reusable cards, status badges, section headers
- `demo_data.py`: deterministic values and reference data
- `workflow_simulator.py`: timer-driven mock state transitions

No scientific computation lives in the UI layer.

## 11. Demo state model

Minimal in-memory state:

```text
ProjectState
- project_name
- project_folder
- baseline_epw
- city
- latitude
- longitude
- project_saved
- climate_saved
- cmip6_progress
- cmip6_running
- factors_complete
- epw_generated
- validation_status
```

A lightweight signal mechanism updates left-navigation status when state changes.

## 12. Error-handling behavior

The mock demo should include controlled examples of:

- invalid baseline EPW message
- GCS timeout -> AWS fallback warning
- paused download state
- scientific fallback warning
- failed validation state preview (optional debug/demo toggle only)

Errors must be represented in-page when possible; message boxes are reserved for confirmations or blocking actions.

## 13. Testing scope for demo

At minimum:

1. App launches without exception.
2. All five pages are reachable from left navigation.
3. Project-save action updates Project status to Complete.
4. Climate-save action updates Climate status to Complete.
5. CMIP6 mock progress can start, pause, and resume.
6. Provider fallback state can be displayed.
7. EPW mock generation reaches expected count.
8. Validation page shows `PASSED WITH WARNINGS` with fallback details.
9. Expected-output count updates when scenario/period/model selections change.
10. No scientific backend module is imported or executed.

## 14. Explicitly out of scope for v0.1

- Real CMIP6 access
- Real cache creation
- Real factor calculation
- Real EPW generation
- Real validation
- EnergyPlus integration
- Multi-computer distributed execution
- Cloud backend
- User accounts
- Database
- Automatic updates
- Map-based point selection
- Arbitrary model/member/grid editing
- Production installer

## 15. Acceptance criteria

The demo is complete when a user can click through the full five-step workflow and understand:

1. what information is required,
2. where the workflow is currently running,
3. what can be paused/resumed,
4. what scientific warnings mean,
5. how many EPWs are expected/generated,
6. whether the final result passed validation.

The UI should be credible enough to decide whether the product flow is correct before backend integration begins.
