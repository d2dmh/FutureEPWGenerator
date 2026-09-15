# Future EPW Generator v1.0 Windows Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the validated v0.9.2.1 Python application into a Windows-installable v1.0.0 desktop release that runs without a user-managed Python environment while preserving Protocol R1 scientific behavior.

**Architecture:** Keep `engine_core` scientifically frozen. Add a packaging/runtime boundary that resolves bundled resources and, when frozen by PyInstaller, re-enters the same executable with a private `--engine-stage` CLI to run Stage 00-05. Build an onedir PyInstaller distribution and wrap it with Inno Setup; provide a Windows GitHub Actions workflow to generate the installer reproducibly.

**Tech Stack:** Python 3.11, PySide6, PyInstaller 6.x, Inno Setup 6, GitHub Actions, existing Stage 00-05 engine.

**Spec:** Approved v1.0 packaging design in chat on 2026-09-15; functional baseline is `Future_EPW_Generator_v0.9.2.1_functional_mvp`.

## Global Constraints

- Do not change CMIP6 extraction, morphing, factor, EPW generation, or validation formulas.
- Preserve Reproducible Mode and Advanced Mode behavior from v0.9.2.1.
- Windows release version is exactly `1.0.0` and application version marker is `1.0.0`.
- Use PyInstaller onedir, not onefile.
- End users must not need Python, pip, Conda, or developer tools.
- Project workspaces remain user-selected and self-contained.
- Application settings/weather-library cache remain outside research projects.
- The packaging workflow must be buildable both locally on Windows and in GitHub Actions.

---

### Task 1: Bundled Resource Paths

**Files:**
- Create: `future_epw_demo/runtime_paths.py`
- Modify: `future_epw_demo/backend.py`
- Modify: `future_epw_demo/weather_library.py`
- Modify: `future_epw_demo/main_window.py`
- Modify: `app.py`
- Test: `tests/test_packaging_runtime.py`

**Interfaces:**
- Produces: `bundle_root() -> Path`, `resource_path(*parts: str) -> Path`, `is_frozen() -> bool`.
- Consumers: backend, catalog, icon loading, VERSION/self-test.

- [ ] Write tests proving source mode resolves the project root and simulated frozen mode resolves `sys._MEIPASS`.
- [ ] Run the focused test and verify it fails before implementation.
- [ ] Implement `runtime_paths.py` and replace direct `Path(__file__)...` resource lookups.
- [ ] Run focused tests and the application suite.

### Task 2: Frozen Engine Stage Dispatch

**Files:**
- Modify: `future_epw_demo/backend.py`
- Modify: `app.py`
- Test: `tests/test_packaging_runtime.py`

**Interfaces:**
- Produces: frozen commands `[FutureEPWGenerator.exe, "--engine-stage", <script>, ...args]`.
- Produces: `run_engine_stage(argv: list[str]) -> int` in `app.py`.

- [ ] Write tests for normal Python command construction and frozen command construction.
- [ ] Run tests and verify frozen command test fails.
- [ ] Add frozen-aware stage command construction without changing stage arguments.
- [ ] Add allowlisted `--engine-stage` dispatch using `runpy.run_path`, temporary engine cwd, and temporary engine path insertion into `sys.path`.
- [ ] Test help/status execution path and rerun the application suite.

### Task 3: v1.0 Product Identity and First-Launch Welcome

**Files:**
- Modify: `VERSION`
- Modify: `future_epw_demo/app_settings.py`
- Create: `future_epw_demo/welcome_dialog.py`
- Modify: `future_epw_demo/main_window.py`
- Modify: `future_epw_demo/i18n.py`
- Modify: `app.py`
- Test: `tests/test_app_settings.py`
- Test: `tests/test_source_contract.py`

**Interfaces:**
- App version: `1.0.0`.
- Settings add `welcome_seen: bool = False`.
- Welcome actions: create project (close dialog), open existing project (delegate to current project-open flow).

- [ ] Write failing tests for version marker and settings migration/default.
- [ ] Implement version and settings migration.
- [ ] Implement bilingual first-launch welcome dialog and schedule it only when no project auto-reopened.
- [ ] Remove visible `Functional MVP` wording in favor of `Version 1.0.0 · Protocol R1`.
- [ ] Rerun application tests.

### Task 4: PyInstaller Onedir Build Definition

**Files:**
- Create: `packaging/FutureEPWGenerator.spec`
- Create: `packaging/windows_version_info.txt`
- Create: `scripts/build_windows.ps1`
- Modify: `requirements-dev.txt`
- Test: `tests/test_packaging_contract.py`

**Interfaces:**
- Output directory: `dist/FutureEPWGenerator/`.
- Entry executable: `FutureEPWGenerator.exe`.
- Bundled data: `assets/`, `engine_core/`, `VERSION`.

- [ ] Write source-contract tests for required packaging files, onedir mode, data inclusion, icon, version resource, and build output path.
- [ ] Add PyInstaller dependency to development requirements.
- [ ] Create spec with explicit data files and collection of scientific runtime dependencies.
- [ ] Create version resource and PowerShell build script that creates a clean venv/build, runs self-test, invokes PyInstaller, and checks the exe exists.
- [ ] Compile/lint Python and run packaging contract tests.

### Task 5: Inno Setup Installer

**Files:**
- Create: `packaging/FutureEPWGenerator.iss`
- Create: `scripts/build_installer.ps1`
- Test: `tests/test_packaging_contract.py`

**Interfaces:**
- Input: `dist/FutureEPWGenerator/**`.
- Output: `release/FutureEPWGenerator_Setup_v1.0.0.exe`.
- Installer creates Start Menu entry, optional desktop shortcut, uninstall entry, and per-user installation under LocalAppData.

- [ ] Add failing contract tests for installer version, output filename, shortcuts, uninstall metadata, and app executable.
- [ ] Implement Inno Setup script.
- [ ] Implement PowerShell installer wrapper with `ISCC.exe` discovery and clear failure message.
- [ ] Run contract tests.

### Task 6: Windows CI Release Build

**Files:**
- Create: `.github/workflows/windows-release.yml`
- Test: `tests/test_packaging_contract.py`

**Interfaces:**
- Manual dispatch and `v*` tags build on `windows-latest`.
- Artifact: `FutureEPWGenerator_Setup_v1.0.0.exe` plus SHA-256.

- [ ] Add failing workflow contract tests.
- [ ] Create workflow: setup Python 3.11, install dependencies, run tests/self-test, install Inno Setup, run packaging scripts, hash installer, upload artifacts.
- [ ] Run contract tests and YAML sanity checks.

### Task 7: Release Documentation and Verification

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Create: `RELEASE_NOTES_v1.0.0.md`
- Create: `WINDOWS_BUILD.md`
- Create: `RELEASE_CHECKLIST_v1.0.0.md`
- Modify: `.gitignore`

**Interfaces:**
- Documents local source run, Windows installer use, Windows build path, CI build path, and known signing limitation.

- [ ] Update docs to make installer the primary end-user path and source run the developer path.
- [ ] Document unsigned-installer SmartScreen behavior explicitly; do not claim code signing.
- [ ] Add build/release directories to `.gitignore`.
- [ ] Run final application suite, engine-core suite, self-test, compileall, source-contract tests, and ZIP integrity check.
- [ ] Package the v1.0 release-engineering source tree and record SHA-256.

