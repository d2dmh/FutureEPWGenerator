# Future EPW Generator v0.9 Functional MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the v0.8 arbitrary-city alpha into a reliable single-city Windows functional MVP that can take a new city's 8760-hour baseline EPW, start at `0/200`, resume interrupted CMIP6 extraction, generate the full future-EPW set, validate it, and restore project state after restart.

**Architecture:** Preserve `engine_core` as the scientific authority and add safety/orchestration around it. `ProjectWorkspace` owns project identity and artifact discovery; new small modules own persistent workflow state, error categories, and generation preflight; existing PySide6 pages call those modules and the existing `WorkflowBackend`/`WorkflowRunner` rather than reimplementing climate science.

**Tech Stack:** Python 3.11+, PySide6, pytest, pandas, xarray/zarr stack already pinned by the project, JSON/CSV project artifacts, existing Stage 00-05 CLI engine.

**Spec:** `docs/superpowers/specs/2026-09-15-future-epw-generator-v0.9-functional-mvp-design.md`

## Global Constraints

- Baseline is `Future_EPW_Generator_v0.8_arbitrary_city_alpha`; do not rewrite the application shell.
- Scientific protocol remains R1: historical 1985-2014; SSP1-2.6, SSP2-4.5, SSP3-7.0; target labels 2040=2030-2050 and 2060=2050-2070; five frozen GCMs; ten frozen variables; bilinear extraction; GCS then AWS; existing BTWS/BWS morphing; five-GCM mean.
- Stage-02 progress contract is exactly `0/200 -> 200/200`; the frozen catalog has 205 rows because 5 additional rows are `sftlf` entries outside the Stage-02 weather-asset count.
- Default Stage-04 output count is 36 EPWs = 3 scenarios x 2 periods x (5 GCMs + ensemble mean).
- GUI/orchestration code must not reproduce or silently alter scientific algorithms.
- Stage 02 must remain resumable through location-specific caches and the existing pause flag.
- Stages 03-05 remain sequential and non-interruptible in v0.9.
- A zero subprocess exit code is not sufficient to mark generation complete; completion comes from real artifacts and validation metadata.
- Existing v0.8 tests must continue to pass.
- Do not add automatic baseline download, batch cities, map selection, accounts/cloud, new SSPs/GCMs, or packaging work in this plan.
- The extracted ZIP used for planning has no `.git` directory. During execution, commit after each task only when running in the real Git working copy; do not initialize a new repository merely to satisfy a commit step.

---

## File/Responsibility Map

**New focused modules**

- `future_epw_demo/errors.py` — typed orchestration errors and user-facing messages; no UI imports.
- `future_epw_demo/workflow_state.py` — `runtime/workflow_state.json` schema, atomic persistence, stale-running recovery, reconciliation with real workspace artifacts.
- `future_epw_demo/preflight.py` — pure generation-preflight checks and report model.

**Existing files to extend**

- `future_epw_demo/project_workspace.py` — safe create/load, baseline fingerprint, artifact truth/completion helpers.
- `future_epw_demo/runner.py` — richer process failure context while retaining QProcess/merged-output behavior.
- `future_epw_demo/backend.py` — command contracts stay stable; v0.9 must not alter scientific CLI arguments unless a failing regression test proves a concrete blocker.
- `future_epw_demo/pages/project_page.py` — explicit Create vs Open behavior and human-readable project errors.
- `future_epw_demo/pages/cmip6_page.py` — persistent Stage-02 state, restart restore, resume/retry semantics.
- `future_epw_demo/pages/generate_page.py` — explicit preflight gate and Stage 03-05 persisted state.
- `future_epw_demo/pages/validation_page.py` — final PASS / PASS WITH WARNINGS / FAIL from real outputs.
- `future_epw_demo/main_window.py` — navigation/status derived from reconciled project state.
- `tests/test_project_safety.py` — project conflict/fingerprint tests.
- `tests/test_workflow_state.py` — persistence/reconciliation tests.
- `tests/test_preflight.py` — blocking preflight tests.
- `tests/test_ui_workflow_contract.py` — lightweight source/Qt contract tests for page behavior where direct UI testing is practical.
- `tests/test_functional_backend.py` — retain and extend existing functional integration coverage.
- `README.md`, `CHANGELOG.md`, `FUNCTIONAL_ACCEPTANCE_CHECKLIST.md` — update only after behavior is verified.

---

### Task 1: Project creation safety and baseline fingerprint

**Files:**
- Create: `future_epw_demo/errors.py`
- Modify: `future_epw_demo/project_workspace.py`
- Create: `tests/test_project_safety.py`
- Regression: `tests/test_functional_backend.py`

**Interfaces:**
- Produces: `ProjectConflictError`, `InvalidBaselineError`, `BaselineFingerprintMismatchError`.
- Produces: `ProjectWorkspace.baseline_path: Path`.
- Produces: `ProjectWorkspace.baseline_sha256() -> str`.
- Produces: `ProjectWorkspace.verify_baseline_fingerprint() -> bool`.
- Persists `project.json["baseline"]` with `relative_path`, `filename`, `sha256`, `hours`, `station`, `wmo`, `latitude`, `longitude`, `elevation`.
- Maintains backward load support for v0.8 `baseline_epw` projects by deriving baseline metadata on first load; do not overwrite the old file until the user saves.

- [ ] **Step 1: Add failing safety/fingerprint tests**

```python
# tests/test_project_safety.py
from pathlib import Path
import json
import pytest

from future_epw_demo.errors import ProjectConflictError, BaselineFingerprintMismatchError
from future_epw_demo.project_workspace import ProjectWorkspace
from tests.test_functional_backend import make_epw

DEFAULTS = dict(
    scenarios=["ssp126", "ssp245", "ssp370"],
    periods=["2040", "2060"],
    gcms=["ACCESS-CM2", "GFDL-ESM4", "MPI-ESM1-2-HR", "IPSL-CM6A-LR", "FGOALS-g3"],
)

def test_create_rejects_existing_future_epw_project(tmp_path: Path):
    epw = make_epw(tmp_path / "source.epw")
    root = tmp_path / "project"
    ProjectWorkspace.create(root=root, project_name="A", baseline_source=epw, **DEFAULTS)
    with pytest.raises(ProjectConflictError):
        ProjectWorkspace.create(root=root, project_name="B", baseline_source=epw, **DEFAULTS)


def test_create_rejects_nonempty_unrelated_directory(tmp_path: Path):
    epw = make_epw(tmp_path / "source.epw")
    root = tmp_path / "occupied"
    root.mkdir()
    (root / "notes.txt").write_text("do not overwrite", encoding="utf-8")
    with pytest.raises(ProjectConflictError):
        ProjectWorkspace.create(root=root, project_name="A", baseline_source=epw, **DEFAULTS)


def test_project_json_stores_baseline_sha256_and_metadata(tmp_path: Path):
    epw = make_epw(tmp_path / "source.epw")
    ws = ProjectWorkspace.create(root=tmp_path / "project", project_name="A", baseline_source=epw, **DEFAULTS)
    payload = json.loads(ws.project_file.read_text(encoding="utf-8"))
    assert payload["baseline"]["sha256"] == ws.baseline_sha256()
    assert payload["baseline"]["hours"] == 8760
    assert payload["baseline"]["relative_path"].startswith("inputs/baseline_epw/")


def test_baseline_replacement_is_detected(tmp_path: Path):
    epw = make_epw(tmp_path / "source.epw")
    ws = ProjectWorkspace.create(root=tmp_path / "project", project_name="A", baseline_source=epw, **DEFAULTS)
    ws.baseline_path.write_text(ws.baseline_path.read_text(encoding="utf-8") + "# changed\n", encoding="utf-8")
    with pytest.raises(BaselineFingerprintMismatchError):
        ws.assert_baseline_integrity()
```

- [ ] **Step 2: Run focused tests and confirm failure**

Run:

```bash
python -m pytest tests/test_project_safety.py -q
```

Expected: collection/import failures for the new error classes and/or missing fingerprint APIs.

- [ ] **Step 3: Implement typed project errors**

```python
# future_epw_demo/errors.py
class WorkflowUserError(RuntimeError):
    code = "WorkflowError"

    def __init__(self, message: str, *, recovery: str = "", progress_safe: bool = True):
        super().__init__(message)
        self.message = message
        self.recovery = recovery
        self.progress_safe = progress_safe

class ProjectConflictError(WorkflowUserError):
    code = "ProjectConflict"

class InvalidBaselineError(WorkflowUserError):
    code = "InvalidBaseline"

class BaselineFingerprintMismatchError(WorkflowUserError):
    code = "BaselineFingerprintMismatch"

class PreflightFailedError(WorkflowUserError):
    code = "PreflightFailed"

class NetworkProviderFailureError(WorkflowUserError):
    code = "NetworkProviderFailure"

class CacheIncompleteError(WorkflowUserError):
    code = "CacheIncomplete"

class BackendProcessFailureError(WorkflowUserError):
    code = "BackendProcessFailure"

class ValidationFailureError(WorkflowUserError):
    code = "ValidationFailure"
```

- [ ] **Step 4: Implement directory safety and fingerprint persistence**

Add to `ProjectWorkspace`:

```python
@property
def baseline_path(self) -> Path:
    return self.baseline_dir / self.baseline_filename

@staticmethod
def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def baseline_sha256(self) -> str:
    return self._sha256_file(self.baseline_path)

def assert_baseline_integrity(self) -> None:
    payload = json.loads(self.project_file.read_text(encoding="utf-8"))
    saved = payload.get("baseline", {}).get("sha256")
    if saved and self.baseline_sha256() != saved:
        raise BaselineFingerprintMismatchError(
            "The baseline EPW no longer matches this project.",
            recovery="Restore the original baseline EPW or create a new project.",
            progress_safe=True,
        )
```

Before any directory creation in `create()`:

```python
if root.exists():
    contents = list(root.iterdir())
    if (root / "project.json").exists():
        raise ProjectConflictError(
            "This folder already contains a Future EPW project.",
            recovery="Open the existing project or choose another folder.",
        )
    if contents:
        raise ProjectConflictError(
            "The selected folder is not empty and is not a Future EPW project.",
            recovery="Choose a new empty project folder.",
        )
```

Change `save()` to write `app_version: "0.9.0-functional-mvp"` and a nested `baseline` object while retaining legacy `baseline_epw` for backward compatibility during v0.9.

- [ ] **Step 5: Run safety plus existing functional tests**

Run:

```bash
python -m pytest tests/test_project_safety.py tests/test_functional_backend.py -q
```

Expected: all pass, including arbitrary-city/location-cache tests.

- [ ] **Step 6: Commit checkpoint when in a Git working copy**

```bash
git add future_epw_demo/errors.py future_epw_demo/project_workspace.py tests/test_project_safety.py tests/test_functional_backend.py
git commit -m "feat: protect projects and fingerprint baseline EPW"
```

If `.git` is absent, do not initialize a repository; record the completed task in the implementation notes and continue.

---

### Task 2: Persistent workflow state store and restart reconciliation

**Files:**
- Create: `future_epw_demo/workflow_state.py`
- Modify: `future_epw_demo/project_workspace.py`
- Create: `tests/test_workflow_state.py`

**Interfaces:**
- Produces: `WorkflowStateRecord` dataclass.
- Produces: `WorkflowStateStore(ws).load() -> WorkflowStateRecord`.
- Produces: `WorkflowStateStore(ws).save(record) -> None` using atomic replace.
- Produces: `WorkflowStateStore(ws).reconcile(active_process=False) -> WorkflowStateRecord`.
- Adds `ProjectWorkspace.workflow_state_file -> Path`.
- Canonical state vocabulary: `not_started`, `ready`, `running`, `pausing`, `paused`, `complete`, `failed`, `warning`.

- [ ] **Step 1: Write failing persistence/restart tests**

```python
# tests/test_workflow_state.py
from dataclasses import replace
from pathlib import Path

from future_epw_demo.workflow_state import WorkflowStateRecord, WorkflowStateStore
from future_epw_demo.project_workspace import ProjectWorkspace
from tests.test_functional_backend import make_epw


def make_ws(tmp_path: Path) -> ProjectWorkspace:
    epw = make_epw(tmp_path / "source.epw")
    return ProjectWorkspace.create(
        root=tmp_path / "project", project_name="Test", baseline_source=epw,
        scenarios=["ssp126", "ssp245", "ssp370"], periods=["2040", "2060"],
        gcms=["ACCESS-CM2", "GFDL-ESM4", "MPI-ESM1-2-HR", "IPSL-CM6A-LR", "FGOALS-g3"],
    )


def test_state_round_trip(tmp_path: Path):
    ws = make_ws(tmp_path)
    store = WorkflowStateStore(ws)
    record = WorkflowStateRecord(current_stage="stage02", state="paused", cmip6_complete=73)
    store.save(record)
    assert store.load().cmip6_complete == 73
    assert store.load().state == "paused"


def test_stale_running_becomes_paused_after_restart(tmp_path: Path):
    ws = make_ws(tmp_path)
    store = WorkflowStateStore(ws)
    store.save(WorkflowStateRecord(current_stage="stage02", state="running", cmip6_complete=0))
    reconciled = store.reconcile(active_process=False)
    assert reconciled.state == "paused"


def test_reconcile_uses_real_partial_cmip6_progress(tmp_path: Path):
    ws = make_ws(tmp_path)
    for i in range(73):
        (ws.cache_dir / f"asset_{i}.csv").write_text("x\n", encoding="utf-8")
    reconciled = WorkflowStateStore(ws).reconcile(active_process=False)
    assert reconciled.cmip6_complete == 73
    assert reconciled.cmip6_total == 200
```

- [ ] **Step 2: Run focused tests and verify failure**

```bash
python -m pytest tests/test_workflow_state.py -q
```

Expected: missing module/types.

- [ ] **Step 3: Implement state schema and atomic save**

```python
# future_epw_demo/workflow_state.py
from __future__ import annotations
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import json
from pathlib import Path

VALID_STATES = {"not_started", "ready", "running", "pausing", "paused", "complete", "failed", "warning"}

@dataclass(frozen=True)
class WorkflowStateRecord:
    schema_version: int = 1
    current_stage: str = ""
    state: str = "not_started"
    last_successful_stage: str = ""
    cmip6_complete: int = 0
    cmip6_total: int = 200
    factors_status: str = "not_started"
    generation_status: str = "not_started"
    validation_status: str = "not_started"
    last_error: dict | None = None
    updated_at: str = ""

class WorkflowStateStore:
    def __init__(self, ws):
        self.ws = ws
        self.path = ws.workflow_state_file

    def save(self, record: WorkflowStateRecord) -> None:
        if record.state not in VALID_STATES:
            raise ValueError(f"Unsupported workflow state: {record.state}")
        payload = asdict(replace(record, updated_at=datetime.now(timezone.utc).isoformat()))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".json.tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.path)
```

Implement `load()` with schema defaults and `reconcile()` using `ws.status_snapshot()` plus the completion helpers added in Task 3. Until Task 3 exists, set factor/generation/validation status from the current snapshot fields; Task 3 will tighten those rules.

- [ ] **Step 4: Add workspace path property**

```python
@property
def workflow_state_file(self) -> Path:
    return self.runtime_dir / "workflow_state.json"
```

- [ ] **Step 5: Run workflow-state tests**

```bash
python -m pytest tests/test_workflow_state.py -q
```

Expected: all pass.

- [ ] **Step 6: Run project regression tests**

```bash
python -m pytest tests/test_project_safety.py tests/test_functional_backend.py tests/test_workflow_state.py -q
```

Expected: all pass.

- [ ] **Step 7: Commit checkpoint when Git is available**

```bash
git add future_epw_demo/workflow_state.py future_epw_demo/project_workspace.py tests/test_workflow_state.py
git commit -m "feat: persist and reconcile workflow state"
```

---

### Task 3: Derive Stage 03-05 completion from real artifacts

**Files:**
- Modify: `future_epw_demo/project_workspace.py`
- Modify: `future_epw_demo/workflow_state.py`
- Modify: `tests/test_workflow_state.py`
- Extend: `tests/test_functional_backend.py`

**Interfaces:**
- Produces: `ProjectWorkspace.expected_epw_count() -> int`.
- Produces: `ProjectWorkspace.factors_complete() -> bool`.
- Produces: `ProjectWorkspace.generation_complete() -> bool`.
- Produces: `ProjectWorkspace.validation_outcome() -> str` returning `not_run`, `pass`, `warning`, or `fail`.
- `WorkflowStateStore.reconcile()` uses these helpers rather than treating a file's mere existence as success.

- [ ] **Step 1: Add failing artifact-truth tests**

```python
def test_factor_metadata_alone_is_not_complete(tmp_path: Path):
    ws = make_ws(tmp_path)
    ws.factors_dir.mkdir(parents=True, exist_ok=True)
    ws.factor_metadata_file.write_text('{"pr_dry_baseline_fallback_rows": 0}', encoding="utf-8")
    assert ws.factors_complete() is False


def test_generation_requires_records_and_all_output_files(tmp_path: Path):
    ws = make_ws(tmp_path)
    ws.epw_dir.mkdir(parents=True, exist_ok=True)
    ws.generation_records_file.write_text("output_epw\nmissing.epw\n", encoding="utf-8")
    assert ws.generation_complete() is False


def test_failed_validation_is_not_complete_success(tmp_path: Path):
    ws = make_ws(tmp_path)
    ws.validation_dir.mkdir(parents=True, exist_ok=True)
    ws.validation_metadata_file.write_text('{"epw_count": 36, "audit_groups": 360, "passed": false}', encoding="utf-8")
    assert ws.validation_outcome() == "fail"
```

- [ ] **Step 2: Run and verify failure**

```bash
python -m pytest tests/test_workflow_state.py -q
```

Expected: missing completion helpers.

- [ ] **Step 3: Implement strict artifact helpers**

`factors_complete()` must require all four Stage-03 outputs and parseable metadata:

```python
required = [
    self.factors_dir / "monthly_climatology_long.csv",
    self.factors_dir / "climate_factors_per_gcm.csv",
    self.factors_dir / "climate_factors_ensemble.csv",
    self.factor_metadata_file,
]
```

`expected_epw_count()`:

```python
def expected_epw_count(self) -> int:
    return len(self.scenarios) * len(self.periods) * (len(self.gcms) + 1)
```

`generation_complete()` must parse `generation_records.csv`, require exactly `expected_epw_count()` rows, require an `output_epw` column, and require every listed EPW path to exist. Treat malformed CSV as incomplete.

`validation_outcome()` must parse `validation_metadata.json`; require `epw_count == expected_epw_count()`. Return `fail` if `passed` is false, `warning` if `passed` is true and Stage-03 `fallback_rows > 0`, otherwise `pass`.

- [ ] **Step 4: Tighten workflow-state reconciliation**

Map real artifacts to persisted states:

```python
factors_status = "complete" if ws.factors_complete() else "not_started"
generation_status = "complete" if ws.generation_complete() else "not_started"
validation_status = {
    "not_run": "not_started",
    "pass": "complete",
    "warning": "warning",
    "fail": "failed",
}[ws.validation_outcome()]
```

Do not mark the whole workflow `complete` unless CMIP6 is `200/200`, factors and generation are complete, and validation is `pass` or `warning`.

- [ ] **Step 5: Run focused and regression tests**

```bash
python -m pytest tests/test_workflow_state.py tests/test_functional_backend.py -q
```

Expected: all pass.

- [ ] **Step 6: Commit checkpoint when Git is available**

```bash
git add future_epw_demo/project_workspace.py future_epw_demo/workflow_state.py tests/test_workflow_state.py tests/test_functional_backend.py
git commit -m "feat: derive completion from scientific artifacts"
```

---

### Task 4: Generation preflight as a pure, blocking gate

**Files:**
- Create: `future_epw_demo/preflight.py`
- Create: `tests/test_preflight.py`
- Modify: `future_epw_demo/project_workspace.py` to add pure integrity helpers used by preflight.

**Interfaces:**
- Produces: `PreflightCheck(name: str, passed: bool, detail: str, blocking: bool=True)`.
- Produces: `PreflightReport(checks: tuple[PreflightCheck, ...])` with `.passed`, `.failures`, and `.as_dict()`.
- Produces: `run_generation_preflight(ws: ProjectWorkspace, *, process_active: bool=False) -> PreflightReport`.
- No Qt imports in this module.

- [ ] **Step 1: Add failing preflight tests**

```python
# tests/test_preflight.py
import json
from pathlib import Path
from future_epw_demo.preflight import run_generation_preflight
from future_epw_demo.project_workspace import ProjectWorkspace
from tests.test_functional_backend import make_epw

def make_preflight_ws(tmp_path: Path, *, cmip6_complete: int) -> ProjectWorkspace:
    epw = make_epw(tmp_path / "source.epw")
    ws = ProjectWorkspace.create(
        root=tmp_path / "project", project_name="Preflight", baseline_source=epw,
        scenarios=["ssp126", "ssp245", "ssp370"], periods=["2040", "2060"],
        gcms=["ACCESS-CM2", "GFDL-ESM4", "MPI-ESM1-2-HR", "IPSL-CM6A-LR", "FGOALS-g3"],
    )
    ws.manifest_file.parent.mkdir(parents=True, exist_ok=True)
    ws.manifest_file.write_text("asset\n" + "\n".join(str(i) for i in range(200)) + "\n", encoding="utf-8")
    ws.cmip6_status_file.write_text(json.dumps({
        "current_city_total": 200,
        "current_city_complete": cmip6_complete,
        "cities": [ws.city],
        "locations": [{"city": ws.city, "latitude": ws.latitude, "longitude": ws.longitude}],
    }), encoding="utf-8")
    return ws

def test_preflight_blocks_incomplete_cmip6(tmp_path: Path):
    ws = make_preflight_ws(tmp_path, cmip6_complete=199)
    report = run_generation_preflight(ws)
    assert report.passed is False
    assert report.as_dict()["CMIP6 cache"].passed is False

def test_preflight_blocks_baseline_hash_mismatch(tmp_path: Path):
    ws = make_preflight_ws(tmp_path, cmip6_complete=200)
    ws.baseline_path.write_text(ws.baseline_path.read_text(encoding="utf-8") + "changed", encoding="utf-8")
    report = run_generation_preflight(ws)
    assert report.passed is False
    assert report.as_dict()["Baseline EPW"].passed is False

def test_preflight_passes_valid_complete_inputs(tmp_path: Path):
    ws = make_preflight_ws(tmp_path, cmip6_complete=200)
    report = run_generation_preflight(ws)
    assert report.passed is True
```

- [ ] **Step 2: Run and verify failure**

```bash
python -m pytest tests/test_preflight.py -q
```

Expected: missing preflight module.

- [ ] **Step 3: Implement explicit checks**

`run_generation_preflight()` must emit these exact display names:

```python
[
    "Project",
    "Baseline EPW",
    "Location",
    "Protocol R1",
    "Manifest",
    "CMIP6 cache",
    "Output directory",
    "Workflow idle",
]
```

Add these pure `ProjectWorkspace` helpers in the same task: `verify_baseline_fingerprint() -> bool`, `location_spec_matches_project() -> bool`, `project_protocol() -> str`, `manifest_row_count() -> int`, and `ensure_output_dirs_writable() -> bool`. They must return false on parse/IO failure rather than raising into the GUI.

Rules:

```python
project_ok = ws.project_file.exists()
baseline_ok = ws.baseline_path.exists() and ws.verify_baseline_fingerprint()
location_ok = ws.location_spec_file.exists() and ws.location_spec_matches_project()
protocol_ok = ws.project_protocol() == "R1"
manifest_ok = ws.manifest_file.exists() and ws.manifest_row_count() == 200
snap = ws.status_snapshot()
cache_ok = snap.cmip6_total == 200 and snap.cmip6_complete == 200 and snap.cmip6_missing == 0
output_ok = ws.ensure_output_dirs_writable()
idle_ok = not process_active
```

For writable-output testing, create and delete a small temporary marker under `outputs/`; never destroy existing outputs.

- [ ] **Step 4: Run preflight and project tests**

```bash
python -m pytest tests/test_preflight.py tests/test_project_safety.py tests/test_functional_backend.py -q
```

Expected: all pass.

- [ ] **Step 5: Commit checkpoint when Git is available**

```bash
git add future_epw_demo/preflight.py future_epw_demo/project_workspace.py tests/test_preflight.py
git commit -m "feat: add blocking generation preflight"
```

---

### Task 5: Runner failure context without changing scientific commands

**Files:**
- Modify: `future_epw_demo/runner.py`
- Create: `tests/test_runner_contract.py`
- Regression: `tests/test_source_contract.py`
- Regression: `tests/test_functional_backend.py` to prove Stage 00-05 command arguments remain unchanged.

**Interfaces:**
- Retains existing `step_started`, `line_received`, `step_finished`, `sequence_finished` signals for page compatibility.
- Adds `failure_reported = Signal(object)` carrying `ProcessFailure`.
- Produces `ProcessFailure(step_name: str, exit_code: int, last_lines: tuple[str, ...], log_file: str)`.
- Produces `WorkflowBackend.download_steps(ws) -> list[ProcessStep]` and `WorkflowBackend.generation_steps(ws) -> list[ProcessStep]` only if these helpers reduce duplicated page logic; they must wrap the same Stage commands already produced by `commands()`.

- [ ] **Step 1: Add failing runner contract tests**

Use a minimal Qt application fixture and a Python child process that exits with code 3 after printing a known message. Assert that `failure_reported` contains the step name, exit code, and recent output. Also retain a source-contract assertion that `QProcess.ProcessChannelMode.MergedChannels` remains configured.

```python
def test_process_failure_contains_recent_output(qapp, tmp_path):
    runner = WorkflowRunner()
    failures = []
    runner.failure_reported.connect(failures.append)
    step = ProcessStep(
        "Stage 02 · CMIP6 extraction",
        [sys.executable, "-c", "print('network failed'); raise SystemExit(3)"],
        tmp_path,
        tmp_path / "stage02.log",
    )
    assert runner.run_sequence([step])
    wait_until(lambda: bool(failures))
    assert failures[0].exit_code == 3
    assert "network failed" in "\n".join(failures[0].last_lines)
```

- [ ] **Step 2: Run and verify failure**

```bash
python -m pytest tests/test_runner_contract.py tests/test_source_contract.py::test_runner_uses_qprocess_and_merged_output -q
```

Expected: missing `failure_reported`/`ProcessFailure`.

- [ ] **Step 3: Buffer recent lines and emit failure report**

Implement a bounded `collections.deque(maxlen=30)` in `WorkflowRunner`. Append each decoded output line in `_read_output()`. On nonzero exit, emit `ProcessFailure` before `sequence_finished(False, name)`.

Do not parse scientific content inside the runner. Provider/status parsing remains in the CMIP6 page/controller.

- [ ] **Step 4: Prove backend command contracts are unchanged**

Do not modify `WorkflowBackend.commands()`. Extend `tests/test_functional_backend.py` with exact assertions that Stage 02 still contains `--location-spec`, `--cache-dir`, `--city-cache-dir`, `--stop-file`, Stage 04 still contains `--selectors ... mean`, and Stage 05 still targets `ws.validation_dir`. This prevents orchestration work from silently changing scientific CLI inputs.

```python
def test_v09_orchestration_keeps_stage_command_contracts(tmp_path: Path):
    # build ws and temporary engine exactly as in test_backend_builds_real_stage_commands
    commands = WorkflowBackend(engine_dir=engine, python_executable="python-test").commands(ws)
    assert ["--location-spec", str(ws.location_spec_file)] == commands.stage02[commands.stage02.index("--location-spec"):commands.stage02.index("--location-spec") + 2]
    assert "--stop-file" in commands.stage02
    assert "--cache-dir" in commands.stage02 and str(ws.cache_dir) in commands.stage02
    assert "--city-cache-dir" in commands.stage02 and str(ws.city_cache_dir) in commands.stage02
    assert "--selectors" in commands.stage04 and "mean" in commands.stage04
    assert str(ws.validation_dir) in commands.stage05
```

- [ ] **Step 5: Run runner/backend regression**

```bash
python -m pytest tests/test_runner_contract.py tests/test_source_contract.py tests/test_functional_backend.py -q
```

Expected: all pass.

- [ ] **Step 6: Commit checkpoint when Git is available**

```bash
git add future_epw_demo/runner.py tests/test_runner_contract.py tests/test_source_contract.py tests/test_functional_backend.py
git commit -m "feat: retain subprocess failure context"
```

---

### Task 6: Project page Create/Open behavior and baseline-integrity messaging

**Files:**
- Modify: `future_epw_demo/pages/project_page.py`
- Modify: `future_epw_demo/main_window.py`
- Create: `tests/test_ui_workflow_contract.py`
- Regression: `tests/test_source_contract.py`

**Interfaces:**
- `ProjectPage._save_project()` handles `WorkflowUserError` categories without showing a traceback.
- Adds an explicit `Open Existing Project…` action that chooses a directory containing `project.json`, loads via `ProjectWorkspace.load()`, validates baseline integrity, and calls `on_project_saved(ws)`.
- `MainWindow._project_saved()` remains the single place that activates a workspace.

- [ ] **Step 1: Add failing UI/source contract tests**

```python
def test_project_page_exposes_open_existing_project_action():
    source = Path("future_epw_demo/pages/project_page.py").read_text(encoding="utf-8")
    assert "Open Existing Project" in source
    assert "ProjectWorkspace.load" in source
    assert "ProjectConflictError" in source or "WorkflowUserError" in source


def test_main_window_still_activates_workspace_through_project_saved():
    source = Path("future_epw_demo/main_window.py").read_text(encoding="utf-8")
    assert "def _project_saved" in source
    assert "self.workspace = ws" in source
```

Also add one direct Qt test if the existing CI environment supports PySide6 headless mode: selecting an already-existing project path and invoking the open helper returns the loaded workspace without creating/copying files.

- [ ] **Step 2: Run focused tests and verify failure**

```bash
python -m pytest tests/test_ui_workflow_contract.py -q
```

Expected: missing Open Existing Project action.

- [ ] **Step 3: Implement Open Existing Project action**

Add a secondary button next to Save Project. The open path must:

```python
root = QFileDialog.getExistingDirectory(self, "Open Future EPW Project")
if not root:
    return
ws = ProjectWorkspace.load(root)
if not ws.verify_baseline_fingerprint():
    QMessageBox.warning(
        self,
        "Baseline EPW changed",
        "This project opened, but its baseline EPW fingerprint no longer matches. Generation will remain blocked until the original baseline is restored.",
    )
self.on_project_saved(ws)
```

On `WorkflowUserError`, show its concise recovery guidance. For malformed `project.json` or IO failure, show `Invalid project` and the exception text; do not modify files. A baseline fingerprint mismatch is a warning on open, not a refusal to open, because the user must be able to inspect the project while generation remains blocked by preflight.

- [ ] **Step 4: Change Save Project behavior for conflicts**

When `ProjectWorkspace.create()` raises `ProjectConflictError`, display:

```text
This folder already contains a Future EPW project.
Open the existing project or choose another folder.
```

Do not auto-open or auto-overwrite; the user's action must be explicit.

- [ ] **Step 5: Run project/UI regression**

```bash
python -m pytest tests/test_ui_workflow_contract.py tests/test_project_safety.py tests/test_source_contract.py -q
```

Expected: all pass.

- [ ] **Step 6: Commit checkpoint when Git is available**

```bash
git add future_epw_demo/pages/project_page.py future_epw_demo/main_window.py tests/test_ui_workflow_contract.py tests/test_source_contract.py
git commit -m "feat: separate project create and open flows"
```

---

### Task 7: CMIP6 page persistent progress, pause/resume, and failed-work retry

**Files:**
- Modify: `future_epw_demo/pages/cmip6_page.py`
- Modify: `future_epw_demo/workflow_state.py`
- Modify: `future_epw_demo/main_window.py`
- Extend: `tests/test_ui_workflow_contract.py`
- Extend: `tests/test_workflow_state.py`

**Interfaces:**
- `CMIP6Page` obtains a `WorkflowStateStore` from the active workspace on each action; it must not cache a store across project switches.
- Resume writes `state="running", current_stage="stage02"` before launching.
- Pause writes `state="pausing"`, creates existing stop flag, and after Stage-02 exits/reconciles stores `paused` if cache < 200.
- Successful status/reconciliation at `200/200` stores `complete` with `last_successful_stage="stage02"`.
- Retry Failed calls the same resume path after reconciliation; no second extraction algorithm.

- [ ] **Step 1: Add failing state transition tests**

Use a fake runner/backend or monkeypatch page methods so no remote request occurs. Assert state writes for Resume, Pause and completion.

```python
def test_retry_failed_reuses_resume_path():
    source = Path("future_epw_demo/pages/cmip6_page.py").read_text(encoding="utf-8")
    assert "def retry_failed" in source
    assert "self.resume()" in source


def test_cmip6_page_uses_workflow_state_store():
    source = Path("future_epw_demo/pages/cmip6_page.py").read_text(encoding="utf-8")
    assert "WorkflowStateStore" in source
    assert 'current_stage="stage02"' in source
```

Add a reconciliation test: persisted `running` + real 73 cache files + no active QProcess becomes `paused` at 73/200 after page refresh/restart.

- [ ] **Step 2: Run and verify failure**

```bash
python -m pytest tests/test_ui_workflow_contract.py tests/test_workflow_state.py -q
```

Expected: missing store usage/transitions.

- [ ] **Step 3: Persist resume/pause state around the existing runner**

At Resume:

```python
store = WorkflowStateStore(ws)
current = store.reconcile(active_process=self.runner.is_running)
store.save(replace(current, current_stage="stage02", state="running", last_error=None))
self.backend.clear_pause_request(ws)
self.runner.run_sequence(self.backend.download_steps(ws))
```

At Pause:

```python
current = store.load()
store.save(replace(current, state="pausing"))
self.backend.request_pause(ws)
```

Do not terminate the process immediately; preserve the existing engine's safe-unit pause semantics.

- [ ] **Step 4: Reconcile after every status/sequence completion**

On `_sequence_finished`, call `store.reconcile(active_process=False)` and show:

- `complete` if actual `200/200`;
- `paused` if stop requested and incomplete;
- `failed` with stage/error metadata for non-pause failures.

`Retry Failed` must call `refresh_from_workspace()` then `resume()`; Stage 02's valid-cache skip logic decides missing work.

- [ ] **Step 5: Preserve provider visibility**

Keep existing parsing of Stage-02 output for current model/scenario/variable/provider/attempt. Provider fallback updates display/provenance but must not set project failure unless the subprocess exits nonzero.

When `failure_reported` arrives, classify a Stage-02 nonzero failure with recent lines containing provider/network phrases as `NetworkProviderFailure`; otherwise classify as `BackendProcessFailure`. Persist the code/message in `last_error` while leaving completed cache safe.

- [ ] **Step 6: Run CMIP6 state/UI regressions**

```bash
python -m pytest tests/test_ui_workflow_contract.py tests/test_workflow_state.py tests/test_source_contract.py tests/test_functional_backend.py -q
```

Expected: all pass.

- [ ] **Step 7: Commit checkpoint when Git is available**

```bash
git add future_epw_demo/pages/cmip6_page.py future_epw_demo/workflow_state.py future_epw_demo/main_window.py tests/test_ui_workflow_contract.py tests/test_workflow_state.py
git commit -m "feat: restore and resume CMIP6 workflow state"
```

---

### Task 8: Generate page preflight gate and persisted Stage 03-05 outcomes

**Files:**
- Modify: `future_epw_demo/pages/generate_page.py`
- Modify: `future_epw_demo/workflow_state.py`
- Extend: `tests/test_ui_workflow_contract.py`
- Extend: `tests/test_preflight.py`

**Interfaces:**
- `GeneratePage.start_generation()` must call `run_generation_preflight(ws, process_active=...)` before starting any process.
- A failed report never calls `runner.run_sequence`.
- A passing report runs existing Stage 03 -> 04 -> 05 commands.
- Reconciliation after sequence completion decides success from artifacts/validation, not from `ok=True` alone.

- [ ] **Step 1: Add failing generate-gate tests**

```python
def test_generate_page_imports_explicit_preflight():
    source = Path("future_epw_demo/pages/generate_page.py").read_text(encoding="utf-8")
    assert "run_generation_preflight" in source
    assert "report.passed" in source


def test_generate_success_is_reconciled_from_workspace_not_exit_code_only():
    source = Path("future_epw_demo/pages/generate_page.py").read_text(encoding="utf-8")
    assert "WorkflowStateStore" in source
    assert "reconcile" in source
```

Add a direct page-level test using a fake runner: monkeypatch `run_generation_preflight` to return a failed `PreflightReport`, call `start_generation()`, and assert `fake_runner.run_sequence_calls == 0`. Define the fake runner with `is_running=False`, `current_step_name=""`, and a `run_sequence()` method that increments the counter.

- [ ] **Step 2: Run and verify failure**

```bash
python -m pytest tests/test_ui_workflow_contract.py tests/test_preflight.py -q
```

Expected: missing preflight integration.

- [ ] **Step 3: Replace visual-only preflight with real report**

`refresh_from_workspace()` may preview preflight, but `start_generation()` must run it again immediately before execution.

Replace the current preflight summary rows with exactly these eight rows: `Project`, `Baseline EPW`, `Location`, `Protocol R1`, `Manifest`, `CMIP6 cache`, `Output directory`, `Workflow idle`. On failure show a single dialog listing failed checks and recovery guidance; leave logs/artifacts untouched.

- [ ] **Step 4: Persist generation state**

Before launching:

```python
store.save(replace(
    store.reconcile(active_process=False),
    current_stage="stage03",
    state="running",
    generation_status="running",
    validation_status="not_started",
    last_error=None,
))
```

On each `step_started`, update `current_stage` to `stage03`, `stage04`, or `stage05`.

On sequence finish, always call `reconcile(active_process=False)`.

- [ ] **Step 5: Enforce final success rules**

If subprocess sequence returns `ok=True` but `ws.generation_complete()` is false or `ws.validation_outcome() == "fail"`, show failure rather than “Workflow complete”.

User-visible outcomes:

```text
PASS
PASS WITH WARNINGS
FAIL
```

Use `ValidationFailureError` for Stage-05 scientific failure and `BackendProcessFailureError` for an earlier nonzero subprocess.

- [ ] **Step 6: Run generate/preflight regression**

```bash
python -m pytest tests/test_ui_workflow_contract.py tests/test_preflight.py tests/test_workflow_state.py tests/test_source_contract.py -q
```

Expected: all pass.

- [ ] **Step 7: Commit checkpoint when Git is available**

```bash
git add future_epw_demo/pages/generate_page.py future_epw_demo/workflow_state.py tests/test_ui_workflow_contract.py tests/test_preflight.py
git commit -m "feat: gate generation with scientific preflight"
```

---

### Task 9: Validation page and main navigation reflect reconciled scientific truth

**Files:**
- Modify: `future_epw_demo/pages/validation_page.py`
- Modify: `future_epw_demo/main_window.py`
- Modify: `future_epw_demo/demo_state.py` to align labels exactly to `PASS`, `PASS WITH WARNINGS`, `FAIL`.
- Extend: `tests/test_ui_workflow_contract.py`
- Extend: `tests/test_demo_state.py`

**Interfaces:**
- Validation page uses `ws.validation_outcome()` and `ws.expected_epw_count()`.
- Main navigation reads `WorkflowStateStore(ws).reconcile(...)` on project activation/page refresh instead of relying only on in-memory `WorkflowState` booleans.
- Preserve `WorkflowState` as lightweight view state for existing GUI bindings; persistent project truth comes from workspace/store.

- [ ] **Step 1: Add failing label/navigation tests**

```python
def test_validation_status_labels_match_v09_contract():
    assert validation_overall_status(hard_checks_pass=True, warning_count=0) == "PASS"
    assert validation_overall_status(hard_checks_pass=True, warning_count=2) == "PASS WITH WARNINGS"
    assert validation_overall_status(hard_checks_pass=False, warning_count=0) == "FAIL"


def test_main_window_reconciles_persistent_state():
    source = Path("future_epw_demo/main_window.py").read_text(encoding="utf-8")
    assert "WorkflowStateStore" in source
    assert ".reconcile(" in source
```

- [ ] **Step 2: Run and verify failure**

```bash
python -m pytest tests/test_demo_state.py tests/test_ui_workflow_contract.py -q
```

Expected: existing labels are `PASSED`/`FAILED` and main window lacks the store.

- [ ] **Step 3: Align user-visible validation labels**

Change only display return values:

```python
def validation_overall_status(*, hard_checks_pass: bool, warning_count: int) -> str:
    if not hard_checks_pass:
        return "FAIL"
    if warning_count > 0:
        return "PASS WITH WARNINGS"
    return "PASS"
```

Keep underlying `validation_passed: bool | None` compatibility until all page code is migrated.

- [ ] **Step 4: Update validation page to strict counts/outcomes**

Use:

```python
expected = ws.expected_epw_count()
outcome = ws.validation_outcome()
```

Display file count only as complete when expected count matches. A false `passed` value must show `FAIL` even if `validation_metadata.json` exists.

- [ ] **Step 5: Reconcile project state in MainWindow**

In `_project_saved`, `_sync_workspace_status`, `set_page`, and `refresh_status`, reconcile state from the store. Map:

- Stage 02 running/paused/complete to CMIP6 navigation status.
- Stage 03-05 running to Generate navigation status.
- validation `warning` to Warning; `complete` to Complete; `failed` to Failed.

Do not mark earlier pages “Complete” solely because the user navigated past them.

- [ ] **Step 6: Run UI/state regression**

```bash
python -m pytest tests/test_demo_state.py tests/test_ui_workflow_contract.py tests/test_workflow_state.py tests/test_source_contract.py -q
```

Expected: all pass.

- [ ] **Step 7: Commit checkpoint when Git is available**

```bash
git add future_epw_demo/pages/validation_page.py future_epw_demo/main_window.py future_epw_demo/demo_state.py tests/test_ui_workflow_contract.py tests/test_demo_state.py
git commit -m "feat: show reconciled scientific workflow status"
```

---

### Task 10: Full local regression, self-test, compile verification, and documentation

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `FUNCTIONAL_ACCEPTANCE_CHECKLIST.md`
- Potentially modify: `app.py` only if self-test needs to cover new pure modules without requiring GUI/network.

**Interfaces:**
- No new runtime interface; this task proves the assembled v0.9 behavior before remote acceptance.

- [ ] **Step 1: Run all project tests from repository root**

```bash
python -m pytest -q
```

Expected: all v0.8 and new v0.9 tests pass. If `engine_core/tests` are intentionally separate because of import-path assumptions, additionally run them from `engine_core/`:

```bash
cd engine_core
python -m pytest -q
cd ..
```

Do not accept a test command that reaches 100% but leaves live child processes indefinitely; if that prior behavior reproduces, identify and close the leaked process/resource before release-candidate status.

- [ ] **Step 2: Run non-GUI self-test**

```bash
python app.py --self-test
```

Expected exact terminal line:

```text
Future EPW Generator functional self-test: PASS
```

Extend self-test only with fast, local assertions: new modules import, expected default EPW count is 36, engine scripts/catalog exist. Do not make self-test contact GCS/AWS.

- [ ] **Step 3: Compile all project Python source**

```bash
python -m compileall -q app.py future_epw_demo engine_core
```

Expected: exit code 0.

- [ ] **Step 4: Update README with the exact v0.9 operator flow**

Document:

```text
Create/Open project -> baseline integrity -> CMIP6 0/200 -> Start/Resume -> 200/200 -> Generate preflight -> Stage 03-05 -> PASS/PASS WITH WARNINGS/FAIL -> reopen project restores state
```

Explicitly state that baseline discovery/download and Windows EXE packaging are not in v0.9.

- [ ] **Step 5: Update changelog and acceptance checklist**

Changelog must list project conflict protection, SHA-256 baseline identity, persistent workflow state, preflight, strict completion, human-readable failure categories, and restart restore.

Acceptance checklist must contain the seven Definition-of-Done conditions from the spec and a place to record actual city, baseline EPW filename/SHA-256, start progress, interruption progress, final 200/200, output count, and final validation outcome.

- [ ] **Step 6: Re-run tests after documentation/self-test changes**

```bash
python -m pytest -q
python app.py --self-test
python -m compileall -q app.py future_epw_demo engine_core
```

Expected: all pass.

- [ ] **Step 7: Commit checkpoint when Git is available**

```bash
git add README.md CHANGELOG.md FUNCTIONAL_ACCEPTANCE_CHECKLIST.md app.py
git commit -m "docs: define v0.9 functional MVP acceptance"
```

Only add `app.py` if it changed.

---

### Task 11: Real uncached-city end-to-end acceptance

**Files:**
- No scientific source change expected.
- Record results in: `FUNCTIONAL_ACCEPTANCE_CHECKLIST.md`
- Save evidence under the test project's own `logs/`, `runtime/`, and `outputs/` directories; do not commit large CMIP6 cache/EPW outputs to Git.

**Interfaces:**
- Exercises the real GUI/backend/engine end-to-end.
- Recommended city: Paris, France, using a reliable Paris-area 8760-hour baseline EPW. Another fresh city is acceptable only if its location-specific cache is confirmed absent.

- [ ] **Step 1: Prepare a truly fresh acceptance workspace**

Choose a new project root with no `project.json` and no location-specific cache. Record baseline EPW filename, station/WMO, coordinates and saved SHA-256 in the checklist.

- [ ] **Step 2: Create project and prove fresh `0/200`**

Open/save the project, run CMIP6 status, and record evidence that the active location reports:

```text
0 / 200
```

If it reports nonzero, inspect `location_key` and cache namespace before continuing; do not delete unrelated scientific data blindly.

- [ ] **Step 3: Start Stage 00-02 and capture real partial progress**

Run until a nonzero partial count is achieved. Record model/scenario/variable/provider and the actual progress value. The reference interruption point may be around 73/200 but no exact number is required.

- [ ] **Step 4: Close the application during partial Stage-02 progress**

Use normal application close. Reopen the same project. Confirm the UI reconciles to the real partial count rather than `0/200` or an incorrect completed state.

- [ ] **Step 5: Resume to `200/200`**

Click Resume and verify previously valid cache work is reused. Confirm final current-location status is exactly:

```text
200 / 200
```

- [ ] **Step 6: Verify provider fallback evidence**

If a natural GCS failure occurs, record the GCS -> AWS log lines and successful continuation. If no natural failure occurs, do not sabotage the scientific run; rely on the deterministic provider-fallback integration/unit coverage and mark the real run as “fallback not naturally triggered.”

- [ ] **Step 7: Run generation preflight**

Require all blocking checks to pass before Stage 03 begins:

```text
Project             PASS
Baseline EPW        PASS
Location            PASS
Protocol R1         PASS
Manifest            PASS
CMIP6 cache         200 / 200
Output directory    PASS
Workflow idle       PASS
```

- [ ] **Step 8: Run Stage 03 -> 04 -> 05**

Do not manually edit factor or generated EPW files. Confirm Stage 04 produces the expected 36 cases under the frozen defaults and Stage 05 writes validation metadata/results.

- [ ] **Step 9: Verify final scientific status**

Accept only:

```text
PASS
```

or, when the engine explicitly documents non-blocking scientific warnings:

```text
PASS WITH WARNINGS
```

`FAIL` blocks v0.9 release even when all subprocesses exited normally.

- [ ] **Step 10: Perform full restart recovery**

Exit the application completely and reopen the project. Confirm without rerunning stages:

```text
CMIP6       200 / 200
Factors     Complete
Future EPW  36 / 36
Validation  PASS or PASS WITH WARNINGS
```

- [ ] **Step 11: Sign off the seven Definition-of-Done conditions**

Mark complete only when all are true:

1. Fresh arbitrary location starts at `0/200`.
2. Real remote extraction reaches `200/200`.
3. Interruption preserves progress and Resume processes missing work.
4. GCS -> AWS fallback is covered without corrupting state.
5. Baseline/location/protocol/manifest/cache pass preflight.
6. Stage 03-05 produce and validate the complete EPW set.
7. Restart restores completed state without rerunning completed work.

- [ ] **Step 12: Commit only the small acceptance record when Git is available**

```bash
git add FUNCTIONAL_ACCEPTANCE_CHECKLIST.md
git commit -m "test: record v0.9 uncached-city acceptance"
```

Do not commit project caches, generated EPWs, logs containing large data dumps, or credentials/proxy settings.

---

## Final Verification Gate

Run from the project root after Task 11:

```bash
python -m pytest -q
python app.py --self-test
python -m compileall -q app.py future_epw_demo engine_core
```

Then verify the real acceptance project restores `200/200`, `36/36`, and `PASS`/`PASS WITH WARNINGS` after restart.

Only after this gate passes should work begin on Windows EXE packaging, installer creation, GitHub release automation, or v1.0 polish.
