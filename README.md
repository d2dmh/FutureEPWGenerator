# Future EPW Generator v1.0.0

A Windows desktop application for producing future EPW weather files from a validated baseline EPW and CMIP6 climate signals. **v1.0.0 is the first packaged-release milestone**: the validated v0.9.2.1 scientific workflow is preserved while Windows distribution is upgraded to a self-contained installer that does not require end users to install Python.

## Download

Windows users should download `FutureEPWGenerator_Setup_v1.0.0.exe` from the repository **Releases** page. Source builds and the reproducible Windows packaging workflow are included in this repository.

## Recommended Windows installation

Install `FutureEPWGenerator_Setup_v1.0.0.exe`, then launch **Future EPW Generator** from the Start Menu or optional desktop shortcut. The installed application bundles its Python/scientific runtime.

The installer produced by the included build pipeline is currently **unsigned**, so Windows SmartScreen may display an unknown-publisher warning. See `WINDOWS_BUILD.md` for build details.

For a local Windows build machine, double-click `BUILD_V1_INSTALLER.bat` (after installing Python 3.11 and Inno Setup 6), or follow `WINDOWS_BUILD.md`.

## v1.0 runtime design

The installed onedir distribution contains `FutureEPWGenerator.exe` for the GUI and `FutureEPWEngine.exe` as the background Stage 00–05 console runner. The split preserves real-time subprocess logs and Stage-02 worker isolation without exposing a command window during normal GUI use.

## Core workflow

```text
Target city + validated 8760-hour baseline EPW
        ↓
Project identity + baseline SHA-256
        ↓
Climate selection
  Reproducible Mode: 5 GCM × 3 SSP × 2040/2060
  Advanced Mode: selected validated GCM/SSP/period subset
        ↓
Stage 00 environment / baseline check
        ↓
Stage 01 selection-specific CMIP6 manifest
        ↓
Stage 02 CMIP6 extraction (GCS → AWS fallback, resumable)
        ↓
Generation preflight
        ↓
Stage 03 climate factors
        ↓
Stage 04 future EPW generation
        ↓
Stage 05 validation
        ↓
PASS / PASS WITH WARNINGS / FAIL
```

## What is new in v0.9.2.1

- Weather Library selection now uses **Search city + bounded result list + station detail + Use/Download button** instead of an editable long combo box.
- The Project page is scrollable, so Weather Library results and Large text size cannot push controls on top of each other.
- The Location card shows **City** and **Station** separately.
- Older projects that persisted the EPW station name as the city now show the catalog city in the UI while preserving the original internal location/cache identity.
- No scientific Stage 00–05 algorithm changed.

## v0.9.2 feature set

### 1. Advanced Mode now controls the real workflow

The Climate page selection is now propagated through Stage 01–05 instead of only changing the displayed expected output count.

Stage-02 asset count is:

```text
selected GCMs × (historical + selected SSPs) × 10 variables
```

Examples:

| Selection | Stage-02 assets | Expected EPWs* |
|---|---:|---:|
| 1 GCM + 1 SSP + 1 period | 20 | 2 |
| 1 GCM + 2 SSP + 1 period | 30 | 4 |
| 2 GCM + 2 SSP + 2 periods | 60 | 12 |
| Reproducible Mode: 5 GCM + 3 SSP + 2 periods | 200 | 36 |

\*One EPW per selected GCM plus one ensemble-mean EPW for each SSP × period combination.

2040/2060 do not increase Stage-02 remote assets because they are cut from the same SSP time series after extraction.

### 2. Reproducible Mode remains frozen

Reproducible Mode still uses:

- SSP1-2.6, SSP2-4.5, SSP3-7.0
- 2040 and 2060 target windows
- ACCESS-CM2, GFDL-ESM4, MPI-ESM1-2-HR, IPSL-CM6A-LR, FGOALS-g3
- ten Amon variables
- 200 Stage-02 weather assets
- 36 future EPWs

The validated BTWS/BWS morphing equations and variable transformations are unchanged.

### 3. Baseline Weather Library

The Project page now offers two baseline sources:

- **Weather Library** — search a bundled catalog of 40 major-city recommended stations, then download/cache the selected TMYx EPW on demand.
- **Local EPW** — browse any validated local 8760-hour EPW as before.

The first catalog includes Beijing, Shanghai, Guangzhou, Shenzhen, Chengdu, Wuhan, Hong Kong, Tokyo, Seoul, Singapore, Delhi, Bangkok, Kuala Lumpur, Jakarta, Manila, Kuwait City, Dubai, Riyadh, London, Paris, Berlin, Madrid, Rome, Amsterdam, Stockholm, Copenhagen, New York, Los Angeles, Chicago, San Francisco, Toronto, Vancouver, Mexico City, Miami, Houston, Sydney, Melbourne, São Paulo, Cairo and Johannesburg.

Weather-library files are **not bundled inside the application ZIP**. The catalog metadata is bundled; EPWs are downloaded only when requested and cached in the user application-data directory. Once selected, the validated EPW is copied into the research project and fingerprinted, so future remote changes do not alter the project baseline.

### 4. City and station are separate

A project now keeps a canonical target city separately from the actual EPW station. For example:

```text
City:    Tokyo
Station: Tokyo.Intl.AP-Haneda.AP
WMO:     476710
```

Known WMO stations in the bundled Weather Library also provide a canonical city suggestion when a local EPW is opened.

### 5. Dynamic progress, ETA and preflight

CMIP6 progress, resumable checkpoints, Remote Data Ready, ETA and generation preflight all use the **active manifest total**, not a hard-coded 200.

A Tokyo smoke-test selection of ACCESS-CM2 + SSP1-2.6 therefore shows:

```text
0 / 20 → 20 / 20
```

rather than `0 / 200`.

## Project safety and reproducibility

- Existing Future EPW project folders are not silently overwritten.
- Baseline EPWs are copied into `inputs/baseline_epw/` and SHA-256 fingerprinted.
- CMIP6 cache is location namespaced and resumable across restarts.
- Changing an Advanced Mode selection preserves compatible CMIP6 cache files.
- Derived outputs from the previous selection are moved under `outputs/stale/<selection-fingerprint>/` rather than silently deleted or reported as current.
- Project provenance records the active GCMs, SSPs, periods and selection-specific manifest metadata.

## Settings

The top-right Settings button provides:

- English / 简体中文
- Small / Standard / Large text size
- Reopen last project automatically
- Show detailed backend log by default

Application settings are stored separately from research-project provenance.

## Developer / source run

For development or scientific debugging from source:

```powershell
python -m pip install -r requirements.txt
python app.py --self-test
python app.py
```

End users should prefer the v1.0 Windows installer. Developers can still use `run_app.bat` when Python is available on PATH.

## Recommended Tokyo smoke test

1. Create a new Tokyo project using the Weather Library or Tokyo Haneda local EPW.
2. Select **Advanced Mode**.
3. Select only `SSP1-2.6`, `2040`, and `ACCESS-CM2`.
4. Save the Climate configuration.
5. The CMIP6 page should report **20 assets**, not 200.
6. Start extraction and verify the Tokyo location-specific cache progresses `0/20`, `1/20`, ... .
7. Pause/reopen to verify resumability.
8. Once complete, Stage 03–05 should expect **2 EPWs** and validate `2/2`.

## Scientific scope

v0.9.2/v0.9.2.1 change workflow **selection and orchestration**, not the scientific morphing equations. The historical reference remains 1985–2014 and the validated scenario/model catalog remains limited to the existing R1 set.

The Weather Library is a convenience layer for acquiring a baseline EPW; the copied project baseline and its hash remain the reproducible scientific input.

## Repository layout

```text
app.py
future_epw_demo/          GUI, project state, Weather Library, orchestration
engine_core/              Stage 00–05 research engine
assets/                   icons + Weather Library catalog
packaging/                PyInstaller + Inno Setup definitions
scripts/                  Windows build scripts
.github/workflows/         Windows release automation
tests/                    application + packaging regression tests
docs/superpowers/         design specs and implementation plans
```

See `RELEASE_NOTES_v1.0.0.md`, `WINDOWS_BUILD.md`, and `RELEASE_CHECKLIST_v1.0.0.md` for release-specific details.
