# Future EPW Generator v1.0.0

v1.0.0 is the first packaged desktop-release milestone for Future EPW Generator. The scientific Protocol R1 workflow is inherited from the validated v0.9.2.1 baseline; this release focuses on Windows distribution, runtime isolation, and release engineering.

## End-user release

The intended Windows artifact is:

`FutureEPWGenerator_Setup_v1.0.0.exe`

The installer deploys a PyInstaller **onedir** application under the current user's LocalAppData Programs directory, creates a Start Menu shortcut, optionally creates a desktop shortcut, and supports normal Windows uninstall.

End users do **not** need Python, Conda, pip, or Inno Setup.

## Frozen runtime architecture

The installed application contains two executables:

- `FutureEPWGenerator.exe` — windowed PySide6 GUI shown to the user.
- `FutureEPWEngine.exe` — hidden console runner used for Stage 00–05 subprocess execution and real-time backend logs.

This separation is intentional: the scientific workflow depends on captured stdout/stderr for progress, fallback telemetry, pause/resume diagnostics, and failure reporting. A windowed-only executable cannot provide that behavior as reliably on Windows.

The GUI launches the engine runner through the private `--engine-stage` interface. Stage arguments are unchanged from the source-mode workflow. Stage 02 worker subprocesses also re-enter `FutureEPWEngine.exe`, preserving isolated asset/city workers in a frozen build.

## Bundled content

The PyInstaller distribution includes:

- PySide6 GUI runtime
- scientific Python dependencies
- `engine_core/` Stage 00–05 workflow
- frozen CMIP6 catalog
- 40-city baseline Weather Library catalog metadata
- application icons and `VERSION`

Weather-library EPW files themselves remain on-demand downloads and are stored in the user's LocalAppData cache. Research projects remain in user-selected project folders.

## Build routes

Two supported Windows build routes are included:

1. Local Windows build using `scripts/build_installer.ps1`.
2. GitHub Actions using `.github/workflows/windows-release.yml`.

A `v1.0.0` tag builds the installer, generates SHA-256, uploads workflow artifacts, and attaches them to the GitHub Release.

## Scientific compatibility

No CMIP6 extraction equation, factor calculation, morphing equation, or EPW validation rule was changed for v1.0.0.

Reproducible Mode remains:

- 5 GCMs
- SSP1-2.6 / SSP2-4.5 / SSP3-7.0
- 2040 / 2060 windows
- 200 Stage-02 assets
- 36 future EPWs

Advanced Mode remains selection-driven as introduced in v0.9.2.

## Signing status

The provided build pipeline produces an **unsigned** Windows installer. Windows SmartScreen may therefore show an unknown-publisher warning. Code signing is intentionally not claimed in v1.0.0 and can be added later with an Authenticode certificate.
