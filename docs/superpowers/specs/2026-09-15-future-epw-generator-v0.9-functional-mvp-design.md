# Future EPW Generator v0.9 — Functional MVP Design Specification

Date: 2026-09-15  
Status: Approved design; implementation not started  
Baseline: `Future_EPW_Generator_v0.8_arbitrary_city_alpha`  
Target: Windows desktop scientific application  
Primary stack: Python + PySide6 + existing CMIP6/EPW research engine

## 1. Product objective

v0.9 turns the v0.8 arbitrary-city alpha into a reliable single-city functional MVP.

The user supplies only:

1. a target city/location label;
2. target coordinates, defaulting to the baseline EPW coordinates; and
3. one reliable 8760-hour baseline EPW.

The application then runs the validated workflow end to end:

`baseline EPW -> environment check -> frozen manifest -> CMIP6 extraction -> climate factors -> future EPW morphing -> validation -> auditable output package`.

The v0.9 success criterion is not that the GUI opens or that individual scripts run. A completely new, uncached location must be able to start at `0/200`, obtain the required CMIP6 data, survive interruption, generate the complete future-EPW set, pass validation, and restore its state after application restart.

## 2. Scope boundaries

### 2.1 In scope

- One target city/location per project.
- Manual selection of a reliable baseline EPW.
- EPW-coordinate mode and explicit-coordinate override mode.
- Arbitrary-city CMIP6 extraction using location-specific caches.
- GCS primary provider with AWS fallback.
- Pause/resume for long-running Stage 02 extraction.
- Persistent workflow state across application restarts.
- Project conflict protection and baseline-file fingerprinting.
- Generation preflight checks.
- Stage 03 -> Stage 04 -> Stage 05 execution using the existing research engine.
- Human-readable error messages with complete technical logs retained.
- End-to-end acceptance using a previously uncached city.
- Preparation for later Windows packaging, without changing the scientific method.

### 2.2 Explicitly out of scope for v0.9

- Automatic baseline-EPW discovery/download.
- Multi-city batch projects.
- User accounts, cloud storage, or server-side execution.
- Map-based location selection.
- New SSPs, GCMs, variables, interpolation methods, or morphing methods.
- Re-design of the v0.5 visual shell.
- AI recommendations for weather files or climate settings.
- Full interruptibility of Stages 03-05.
- Cloud/API productization.

These remain future-version work. They must not expand v0.9 implementation scope.

## 3. Scientific protocol freeze

The existing Protocol R1 scientific workflow remains authoritative. GUI and orchestration work must not silently modify scientific calculations.

Frozen defaults:

- Historical window: 1985-2014.
- Scenarios: SSP1-2.6, SSP2-4.5, SSP3-7.0.
- Future labels/windows: 2040 = 2030-2050; 2060 = 2050-2070.
- GCMs:
  - ACCESS-CM2
  - GFDL-ESM4
  - MPI-ESM1-2-HR
  - IPSL-CM6A-LR
  - FGOALS-g3
- Required climate variables: `tas`, `tasmax`, `tasmin`, `huss`, `psl`, `sfcWind`, `clt`, `rsds`, `rlds`, `pr`.
- Spatial extraction/interpolation: existing bilinear workflow.
- Provider order: GCS primary -> AWS fallback.
- Temperature morphing: existing BTWS implementation.
- Solar/cloud morphing: existing BWS implementation.
- Humidity, pressure, wind, precipitation and dry-baseline fallback: existing engine behavior.
- Ensemble: five-GCM mean.

The frozen catalog contains 205 rows: 200 Stage-02 weather assets plus 5 `sftlf` land-fraction entries used by the wider frozen workflow. The GUI Stage-02 progress contract remains `0/200 -> 200/200` for one target location.

With the default 3 scenarios x 2 future periods x (5 GCMs + ensemble mean), Stage 04 is expected to generate 36 future EPW cases for one city.

## 4. Architectural rule

v0.9 preserves a strict separation between product orchestration and scientific computation.

```text
PySide6 GUI
    |
    v
Project Manager
    |
    v
Workflow Controller
    |-- persistent state
    |-- preflight
    |-- error classification
    |-- log routing
    v
WorkflowBackend / Engine Adapter
    |
    v
--------------------------------
Frozen Research Engine
Stage 00 -> 01 -> 02 -> 03 -> 04 -> 05
--------------------------------
    |
    v
Project Workspace + location-specific cache + outputs
```

Rules:

1. GUI code does not implement climate science.
2. Workflow controller decides what may run and records state; it does not reproduce Stage 00-05 algorithms.
3. Engine scripts remain executable independently from the GUI.
4. Scientific changes, if later required, must be versioned explicitly rather than hidden inside UI work.

## 5. Existing code retained

The following v0.8 structure is retained rather than rewritten:

- `future_epw_demo/project_workspace.py` — project paths, location identity, status snapshots.
- `future_epw_demo/backend.py` — construction of Stage 00-05 CLI commands.
- `future_epw_demo/runner.py` — QProcess execution and log capture.
- `future_epw_demo/pages/project_page.py` — project creation/opening UI.
- `future_epw_demo/pages/cmip6_page.py` — Stage 00-02 controls and live progress.
- `future_epw_demo/pages/generate_page.py` — Stage 03-05 controls.
- `future_epw_demo/pages/validation_page.py` — real validation outputs and project export.
- `engine_core/00_check_environment.py` through `05_validate_outputs.py` — research engine.

v0.9 adds control, persistence, safety and acceptance logic around these components.

## 6. Project Manager design

### 6.1 Project creation safety

`ProjectWorkspace.create()` must not silently overwrite an existing project or unrelated directory contents.

Creation rules:

1. Non-existent or empty target directory -> allow project creation.
2. Directory containing `project.json` -> do not create/overwrite; offer/open as an existing Future EPW project.
3. Non-empty directory without `project.json` -> block creation and request another directory.
4. Copying the selected baseline EPW must not overwrite a different existing baseline file silently.

### 6.2 Baseline fingerprint

`project.json` must persist a baseline identity sufficient to detect accidental file replacement. At minimum:

```json
{
  "baseline": {
    "relative_path": "inputs/baseline_epw/example.epw",
    "filename": "example.epw",
    "sha256": "...",
    "hours": 8760,
    "station": "...",
    "wmo": "...",
    "latitude": 0.0,
    "longitude": 0.0,
    "elevation": 0.0
  }
}
```

On project load, v0.9 recalculates the fingerprint. A mismatch is a blocking preflight error until the user restores the original baseline or deliberately creates a new project.

### 6.3 Location identity

v0.9 preserves the v0.8 `location_key` behavior based on city label plus target latitude/longitude rounded to the existing precision and hashed.

Consequences:

- A genuinely new location cannot appear complete because another city's cache exists.
- The same city label at different coordinates is treated as a different cache namespace.
- Renaming a city at identical coordinates may create a separate cache namespace; this is acceptable in v0.9 because it favors safety over cache deduplication.

No cache-identity migration is introduced in v0.9.

## 7. Persistent workflow controller

### 7.1 Persistent state file

Add:

`runtime/workflow_state.json`

This file records orchestration state only. Scientific truth continues to be checked against actual files and Stage outputs.

Minimum schema:

```json
{
  "schema_version": 1,
  "current_stage": "stage02",
  "state": "paused",
  "last_successful_stage": "stage01",
  "cmip6_complete": 73,
  "cmip6_total": 200,
  "factors_status": "not_started",
  "generation_status": "not_started",
  "validation_status": "not_started",
  "last_error": null,
  "updated_at": "ISO-8601 timestamp"
}
```

### 7.2 Canonical workflow states

Use a small state vocabulary:

- `not_started`
- `ready`
- `running`
- `pausing`
- `paused`
- `complete`
- `failed`
- `warning`

The controller must not infer `complete` only from a prior GUI session. On project open it reconciles the persisted state with real workspace outputs using `ProjectWorkspace.status_snapshot()` and targeted preflight checks.

### 7.3 Restart behavior

After application restart:

- CMIP6 progress is reconstructed from the location-specific cache/status file.
- Stage 03 completion is reconstructed from factor metadata and required factor files.
- Stage 04 completion is reconstructed from generation records plus expected output count.
- Stage 05 completion is reconstructed from validation metadata/results.
- Stale `running` state from a terminated application is converted to a recoverable `paused` or `failed` state based on real outputs; it must never remain indefinitely `running`.

## 8. Stage 02 download manager

### 8.1 Existing scientific/data behavior retained

Stage 02 continues to use:

- location-specific asset and city checkpoint caches;
- GCS -> AWS provider fallback;
- per-provider hard timeout;
- existing retries;
- pause flag checked between safe work units;
- cache validity checks before remote extraction.

### 8.2 Resume semantics

Resume means:

1. preserve already valid asset/city cache files;
2. re-scan actual cache state;
3. process only missing/incomplete work;
4. never restart valid completed work solely because the GUI was closed.

`Retry Failed` in v0.9 may internally reuse the same Stage-02 resume command. Since Stage 02 already skips valid cache entries, re-running it naturally targets missing/previously failed work. v0.9 does not require a second scientific extraction path only for failed assets.

### 8.3 Progress display

The CMIP6 page must show, where available:

- complete / total (`N/200`);
- current model;
- current scenario;
- current variable;
- current city/location;
- current provider;
- retry/attempt information;
- paused/running/failed/complete status.

Provider fallback is informative, not itself a project failure. A work item becomes failed only when all configured providers/retries fail and Stage 02 exits unsuccessfully.

## 9. Generation preflight

The Generate action must run an explicit preflight before Stage 03.

Blocking checks:

1. `project.json` exists and can be parsed.
2. Baseline EPW exists and matches its saved SHA-256 fingerprint.
3. Baseline EPW parses as a valid 8760-hour EPW with LOCATION metadata.
4. Location specification exists and matches the active project city/coordinates.
5. Protocol/configuration is the expected R1 configuration for the active project.
6. Manifest exists and is readable.
7. Current-location Stage-02 coverage is exactly complete (`200/200` under the frozen v0.9 protocol).
8. Required output directories are writable.
9. No other workflow process is active.

If any blocking check fails, Stage 03 must not start.

The GUI shows a compact preflight report, for example:

```text
Baseline EPW        PASS
Location            PASS
Protocol R1         PASS
Manifest            PASS
CMIP6 cache         200 / 200
Output directory    PASS
```

## 10. Stage 03-05 behavior

### 10.1 No invasive pause feature

Stage 03-05 remain a sequential local chain in v0.9:

`Stage 03 -> Stage 04 -> Stage 05`

v0.9 does not add mid-stage interruption to these scripts.

### 10.2 Completion rules

- Stage 03 is complete only when expected factor outputs and factor metadata are present and readable.
- Stage 04 is complete only when `generation_records.csv` is consistent with the expected case count and the expected EPW files exist.
- Stage 05 is complete only when validation metadata/results exist and give a final validation outcome.
- A process exit code of zero alone is not sufficient to mark the whole workflow complete.

### 10.3 Re-run behavior

A failed local chain may be re-run safely. The controller determines the earliest stage that must be repeated based on real artifacts. v0.9 prioritizes correctness and deterministic regeneration over complex partial-stage resume logic.

## 11. Validation contract

The final product status is based on scientific output validation, not on absence of a Python exception.

For the default configuration, expected generation is 36 EPW cases.

Validation must establish, using the existing Stage 05 outputs and any necessary orchestration checks:

- expected EPW case count;
- readable EPW files;
- 8760 hourly records per file;
- no unacceptable missing/NaN values in required fields;
- physical/range checks already implemented by Stage 05;
- audit/target-vs-achieved checks already implemented by Stage 05;
- consistent metadata/provenance.

GUI-level final states:

- `PASS`
- `PASS WITH WARNINGS`
- `FAIL`

A scientific validation failure is never displayed as successful generation merely because Stage 05 completed execution.

## 12. Error handling and logging

### 12.1 User-facing error classes

v0.9 introduces a small orchestration-level taxonomy, for example:

- `ProjectConflict`
- `InvalidBaseline`
- `BaselineFingerprintMismatch`
- `PreflightFailed`
- `NetworkProviderFailure`
- `CacheIncomplete`
- `BackendProcessFailure`
- `ValidationFailure`

The exact Python class layout may vary, but these user-visible categories must remain distinguishable.

### 12.2 Error presentation

Default dialogs must explain:

1. what failed;
2. whether existing progress is safe;
3. what the user should do next.

Example:

```text
CMIP6 download could not continue.
Completed progress has been preserved: 73 / 200.
Both configured providers failed for the current work item.
Check network/proxy access and click Resume to continue.
```

### 12.3 Technical evidence retained

Human-readable messages do not replace technical diagnostics.

- Full subprocess stdout/stderr continues to be written under `logs/`.
- Error state records the failed stage and a concise machine-readable reason.
- The GUI retains a “show detailed log/technical details” path.

## 13. UI behavior changes

v0.9 retains the existing five-page navigation:

1. Project
2. Climate
3. CMIP6
4. Generate
5. Validation

No visual redesign is required.

Required behavioral changes:

- Project page distinguishes Create New Project from Open Existing Project behavior.
- CMIP6 page restores persisted progress/state on open.
- Generate button is disabled or blocked until preflight passes.
- Validation page shows final `PASS`, `PASS WITH WARNINGS`, or `FAIL` based on real outputs.
- Navigation status reflects real workspace state rather than only in-memory UI events.

## 14. Test strategy

Implementation must extend, not replace, the existing test suite.

### 14.1 Unit/integration tests

Required coverage includes:

- empty-directory project creation succeeds;
- existing Future EPW project cannot be silently overwritten;
- non-empty unrelated directory is rejected;
- baseline SHA-256 is stored and verified;
- fingerprint mismatch blocks generation;
- different coordinates create isolated location caches;
- status from another location cannot mark a project complete;
- stale running state is recovered after restart;
- partial CMIP6 state restores correctly;
- generation preflight blocks at less than 200/200;
- generation preflight passes at valid 200/200 state;
- local Stage 03-05 completion is derived from real artifacts;
- failed validation cannot become GUI success;
- existing Stage 00-05 command contracts remain intact.

### 14.2 Regression requirements

At minimum, before release candidate status:

- all existing v0.8 tests pass;
- all new v0.9 tests pass;
- `python app.py --self-test` passes;
- project source compiles cleanly with `compileall`;
- no test relies on the old eight-city map as an arbitrary-city gate.

## 15. End-to-end acceptance test

### 15.1 Test location

Use a city/location that has no existing project cache in the test workspace. Paris is the recommended reference acceptance case, but the criterion is “fresh uncached location,” not the city name itself.

Example:

- Project label: Paris
- Reliable Paris-area baseline EPW
- EPW coordinates or explicitly confirmed target coordinates

### 15.2 Required sequence

1. Create the project in a clean directory.
2. Verify baseline metadata and fingerprint.
3. Run Stage-02 status and confirm `0/200` for the fresh location.
4. Start real Stage 00 -> 01 -> 02 workflow.
5. During extraction, stop/close the application after nonzero partial progress, e.g. around `73/200`.
6. Reopen the project.
7. Confirm the actual partial progress is restored rather than reset to zero.
8. Resume and reach `200/200`.
9. Confirm GCS -> AWS fallback is observable if a provider failure occurs; if it does not occur naturally, cover fallback deterministically in an integration test rather than corrupting scientific outputs.
10. Run Generate preflight and require all checks to pass.
11. Execute Stage 03 -> 04 -> 05.
12. Confirm the complete expected EPW set (36 under the frozen default configuration).
13. Confirm validation final state is acceptable (`PASS`, or `PASS WITH WARNINGS` only where warnings are scientifically non-blocking and explicitly reported).
14. Exit the application completely.
15. Reopen the project and confirm persistent state reports:

```text
CMIP6       200 / 200
Factors     Complete
Future EPW  36 / 36
Validation  PASS or PASS WITH WARNINGS
```

### 15.3 Definition of Done

v0.9 is complete only when all seven conditions hold:

1. A previously uncached arbitrary location correctly starts at `0/200`.
2. Real remote extraction can reach `200/200` for that location.
3. Stage-02 interruption preserves valid progress and Resume continues missing work.
4. GCS failure can fall back to AWS without corrupting project state.
5. Baseline, location, protocol, manifest and cache all pass generation preflight.
6. Stage 03-05 produce and validate the complete future-EPW output set.
7. Application restart restores the completed project's state without rerunning completed work.

No subset of these conditions is sufficient for v0.9 release.

## 16. Expected implementation areas

The implementation plan should concentrate changes in the smallest practical set of files, expected to include:

- `future_epw_demo/project_workspace.py`
- `future_epw_demo/runner.py`
- `future_epw_demo/backend.py`
- `future_epw_demo/pages/project_page.py`
- `future_epw_demo/pages/cmip6_page.py`
- `future_epw_demo/pages/generate_page.py`
- `future_epw_demo/pages/validation_page.py`
- a new small workflow-state/preflight module if this keeps responsibilities isolated
- `tests/test_functional_backend.py`
- additional focused v0.9 tests as needed
- README/changelog only after behavior is implemented and verified

Changes to `engine_core` are not expected unless a test demonstrates a concrete blocker. Any engine change must be minimal, scientifically neutral, regression-tested, and documented separately.

## 17. Release sequencing after v0.9

Only after the functional MVP passes the acceptance test should the project move to:

1. Windows executable packaging;
2. installer creation;
3. GitHub-ready release structure and documentation;
4. v1.0 release candidate testing.

Packaging work must not be used to hide unresolved v0.9 workflow defects.
