# Future EPW Generator v0.9.2 — Functional Acceptance Checklist

## A. Reproducible Mode regression

- [ ] Open/create a project with a valid 8760-hour baseline EPW.
- [ ] Reproducible Mode locks 5 GCMs, 3 SSPs, 2040 + 2060.
- [ ] Climate page reports 200 CMIP6 assets and 36 expected EPWs.
- [ ] Existing v0.9.1 location cache is recognized when compatible.
- [ ] Stage 03–05 validation can still PASS with 36/36 EPWs.

## B. Tokyo Advanced Mode smoke test

- [ ] Create `Tokyo_Future_EPW` using Tokyo Haneda (WMO 476710).
- [ ] City shows `Tokyo`; station shows the actual Haneda station name.
- [ ] Select Advanced Mode: ACCESS-CM2 + SSP1-2.6 + 2040 only.
- [ ] Save selection; CMIP6 page reports 20 assets.
- [ ] Fresh location shows `0 / 20` unless compatible cache already exists.
- [ ] Stage 01 writes a 20-row manifest with matching selection metadata.
- [ ] Stage 02 progresses against `/20`, not `/200`.
- [ ] Pause/reopen preserves completed assets/checkpoints.
- [ ] ETA uses the 20-asset active manifest.
- [ ] Stage 03 uses only ACCESS-CM2 / SSP126 / 2040.
- [ ] Stage 04 expects 2 EPWs: ACCESS-CM2 + ensemble mean.
- [ ] Stage 05 can PASS with 2/2 valid EPWs.

## C. Weather Library

- [ ] Search `Tokyo`, `东京`, `Haneda`, or `476710` and resolve the Tokyo station.
- [ ] `Download & Use` downloads or reuses the global cached EPW.
- [ ] Downloaded EPW validates at 8760 hours, correct WMO and coordinates.
- [ ] Project stores a copied baseline EPW and SHA-256 fingerprint.
- [ ] Reopening the project does not depend on the remote source.
- [ ] Local EPW Browse still works without the Weather Library.
- [ ] A corrupt archive or WMO mismatch shows a user-facing error and does not replace an existing project baseline.

## D. Selection changes

- [ ] Changing an Advanced Mode selection preserves compatible CMIP6 cache files.
- [ ] Active manifest/factors/EPW validation state becomes stale.
- [ ] Previous derived outputs are preserved under `outputs/stale/<selection-fingerprint>/`.
- [ ] New CMIP6 progress counts only assets belonging to the new selection.

## E. Settings and UI

- [ ] English / 简体中文 applies to new v0.9.2 controls.
- [ ] Small / Standard / Large text size still works.
- [ ] Reopen-last-project still works.
- [ ] Complete assets, checkpoints, Remote Data Ready and ETA remain internally consistent.
