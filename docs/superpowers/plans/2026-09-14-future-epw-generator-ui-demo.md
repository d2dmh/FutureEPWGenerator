# Future EPW Generator UI Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Build a clickable PySide6 Windows desktop UI demo for the approved five-stage Future EPW Generator workflow using deterministic mock data only.

**Architecture:** Keep GUI presentation separate from deterministic workflow state. `future_epw_demo/demo_state.py` owns calculations and mock state transitions; `future_epw_demo/main_window.py` owns the shell/navigation; each page lives in `future_epw_demo/pages/`. No real CMIP6, EPW generation, filesystem project creation, or scientific backend execution occurs in v0.1.

**Tech Stack:** Python 3.12+, PySide6 6.x, standard library, pytest for pure-state tests.

**Spec:** `docs/superpowers/specs/2026-09-14-future-epw-generator-ui-demo-design.md`

## Global Constraints

- Windows desktop demo; PySide6 UI.
- Scientific-tool style: white background, light-gray cards, restrained blue accents, no decorative gradients.
- Five left-nav stages: Project, Climate, CMIP6, Generate, Validation.
- Recommended/Reproducible Mode is default.
- Demo runtime is deterministic mock data only; do not call real CMIP6 providers or scientific backend.
- Expected EPW count is dynamic: cities × scenarios × periods × (GCMs + ensemble).
- Advanced Mode is visual/read-only in v0.1.
- CMIP6 progress supports mock pause/resume/status and visible GCS→AWS fallback.
- Validation distinguishes PASSED / PASSED WITH WARNINGS / FAILED.
- Preserve the real reference QA values in demo copy where specified: 33,600 climatology rows, 2,880 per-GCM rows, 2,880 ensemble rows, 6 precipitation fallback records, 288/288 reference EPWs, 2,880 audit groups.

---

### Task 1: Deterministic Demo State Model

**Files:**
- Create: `future_epw_demo/__init__.py`
- Create: `future_epw_demo/demo_state.py`
- Test: `tests/test_demo_state.py`

**Interfaces:**
- Produces: `WorkflowState`, `expected_epw_count()`, `configuration_fingerprint()`, `validation_overall_status()`.
- GUI pages consume these functions and the mutable `WorkflowState` instance.

- [x] **Step 1: Write failing tests** for default 36-EPW single-city count, reduced selections, configuration fingerprint, warning-level validation, CMIP6 progress/pause/resume, and provider fallback.
- [x] **Step 2: Run `python -m pytest tests/test_demo_state.py -q` and confirm RED** because `future_epw_demo.demo_state` does not exist.
- [x] **Step 3: Implement the minimal pure-Python state model** with the exact defaults in the spec.
- [x] **Step 4: Re-run `python -m pytest tests/test_demo_state.py -q` and confirm GREEN.**

### Task 2: Main Shell and Scientific Theme

**Files:**
- Create: `future_epw_demo/theme.py`
- Create: `future_epw_demo/widgets.py`
- Create: `future_epw_demo/main_window.py`
- Create: `app.py`
- Test: `tests/test_source_contract.py`

**Interfaces:**
- `MainWindow(state: WorkflowState)` creates the top bar, left workflow nav, stacked pages, and bottom status bar.
- `app.py` launches the PySide6 application; `python app.py --self-test` runs pure state assertions without importing PySide6.

- [x] **Step 1: Write source-contract tests** asserting the five nav labels, app title, and self-test entrypoint contract exist.
- [x] **Step 2: Run the source-contract tests and confirm RED.**
- [x] **Step 3: Implement the shell, shared card helpers, styles, and entrypoint.**
- [x] **Step 4: Run source-contract tests and `python app.py --self-test`; confirm GREEN.**

### Task 3: Project and Climate Pages

**Files:**
- Create: `future_epw_demo/pages/__init__.py`
- Create: `future_epw_demo/pages/project_page.py`
- Create: `future_epw_demo/pages/climate_page.py`
- Test: `tests/test_source_contract.py`

**Interfaces:**
- `ProjectPage(state, on_next)` exposes demo EPW metadata and coordinate-lock behavior.
- `ClimatePage(state, on_next, on_back)` exposes Recommended/Advanced modes, default scenarios/periods/GCMs, scientific config, dynamic output count, and fingerprint.

- [x] **Step 1: Extend source-contract tests** with required labels and default scientific-method text.
- [x] **Step 2: Run and confirm RED.**
- [x] **Step 3: Implement both pages with mock browse actions and dynamic count updates.**
- [x] **Step 4: Run tests and self-test; confirm GREEN.**

### Task 4: CMIP6, Generate, and Validation Pages

**Files:**
- Create: `future_epw_demo/pages/cmip6_page.py`
- Create: `future_epw_demo/pages/generate_page.py`
- Create: `future_epw_demo/pages/validation_page.py`
- Modify: `future_epw_demo/main_window.py`
- Test: `tests/test_source_contract.py`

**Interfaces:**
- `CMIP6Page` uses a `QTimer` to advance deterministic mock progress and demonstrates one GCS timeout/AWS fallback.
- `GeneratePage` presents Stage 03 reference rows, six precipitation warnings, mock EPW generation progress, factor/warning dialogs.
- `ValidationPage` presents hard QA separately from scientific warnings and offers mock export/open-folder actions.

- [x] **Step 1: Extend source-contract tests** for required progress labels, warning copy, validation states, and output actions.
- [x] **Step 2: Run and confirm RED.**
- [x] **Step 3: Implement the three pages and wire them into the main window.**
- [x] **Step 4: Run all tests and self-test; confirm GREEN.**

### Task 5: Packaging, Documentation, and Verification

**Files:**
- Create: `requirements.txt`
- Create: `README.md`
- Create: `run_demo.bat`
- Create: `DEMO_ACCEPTANCE_CHECKLIST.md`

**Interfaces:**
- User runs `run_demo.bat` or `python app.py` after installing requirements.
- README must explicitly say v0.1 is mock-only and does not invoke the production scientific backend.

- [x] **Step 1: Add packaging/docs files** with Windows setup and run instructions.
- [x] **Step 2: Run `python -m pytest -q`, `python app.py --self-test`, and `python -m compileall -q app.py future_epw_demo tests`.**
- [x] **Step 3: Check the spec line-by-line against the acceptance checklist and record any unverified GUI-runtime limitation caused by missing PySide6 in the build sandbox.**
- [x] **Step 4: Create `Future_EPW_Generator_UI_Demo_v0.1.zip` from the verified source tree.**
