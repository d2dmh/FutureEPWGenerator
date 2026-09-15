# Future EPW Generator v1.0.0 Release Checklist

## Source verification

- [ ] `python app.py --self-test` passes.
- [ ] `python -m pytest -q tests` passes.
- [ ] `engine_core` full tests pass.
- [ ] `python -m compileall` passes.

## Windows build verification

- [ ] `scripts/build_windows.ps1` finishes successfully on Windows x64.
- [ ] `FutureEPWGenerator.exe` launches without Python installed globally.
- [ ] `FutureEPWEngine.exe --self-test` passes.
- [ ] New project can be created using a local EPW.
- [ ] Weather Library can download and validate a baseline EPW.
- [ ] Advanced Mode `1 GCM + 1 SSP` reports 20 assets.
- [ ] Stage 02 logs stream into the GUI from the frozen engine runner.
- [ ] Pause → close → reopen → Resume preserves cache progress.
- [ ] Stage 03–05 generate and validate the expected EPW count.

## Installer verification

- [ ] `FutureEPWGenerator_Setup_v1.0.0.exe` installs for the current user.
- [ ] Start Menu shortcut launches the GUI.
- [ ] Optional desktop shortcut launches the GUI.
- [ ] Settings persist across application restarts.
- [ ] Uninstall removes the application binaries.
- [ ] Existing research projects remain untouched after uninstall.

## Release verification

- [ ] SHA-256 file matches installer.
- [ ] `v1.0.0` GitHub tag builds successfully.
- [ ] GitHub Release contains installer and SHA-256.
- [ ] Release notes clearly state that the installer is unsigned.
