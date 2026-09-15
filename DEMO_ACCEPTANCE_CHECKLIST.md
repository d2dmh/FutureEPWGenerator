# Future EPW Generator v0.9.2 — UI Acceptance Checklist

## Shell
- [ ] Window/taskbar icon renders correctly.
- [ ] English / 简体中文 switch correctly from Settings.
- [ ] Small / Standard / Large text sizes remain readable at 1280×800.
- [ ] Last valid project can reopen automatically when enabled.

## Project
- [ ] Weather Library and Local EPW source modes are visible.
- [ ] Weather Library supports city / station / WMO search.
- [ ] Selected catalog record shows city, station, WMO, period, source and cache state.
- [ ] Download & Use / Use Cached actions work.
- [ ] City summary updates to the canonical target city rather than a stale template value.
- [ ] Station metadata remains the actual EPW station.

## Climate
- [ ] Reproducible Mode locks the full 5-GCM / 3-SSP / 2-period matrix.
- [ ] Advanced Mode enables validated subset selection.
- [ ] Live summary updates SSP count, periods, GCM count, asset count, output count and fingerprint.
- [ ] Empty Advanced selections are rejected.

## CMIP6
- [ ] Active asset denominator matches the selection (for example 20, not always 200).
- [ ] Complete Assets, Pending, Failed, City Checkpoints and Remote Data Ready are consistent.
- [ ] ETA uses the active denominator.
- [ ] Pause / Resume / Retry Failed / Check Status remain usable.
- [ ] Detailed backend log remains available.

## Generate
- [ ] Preflight includes the active Climate selection.
- [ ] Manifest and cache checks use the dynamic asset total.
- [ ] Expected EPW count matches the active selection.
- [ ] Stage 03–05 can complete a custom subset without requiring full 36-output coverage.

## Validation
- [ ] Hard QA, scientific warnings and provenance remain visually distinct.
- [ ] Validation detail table reflects the dynamic output count.
- [ ] PASS / PASS WITH WARNINGS / FAIL comes from real Stage-05 project artifacts.
