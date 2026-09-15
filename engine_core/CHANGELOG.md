# Changelog

## v1.5.0 — 2026-09-13

- Added `02b_coastal_sensitivity.py` for an explicit standard-bilinear vs `sftlf`-weighted sensitivity analysis focused on Singapore, Sydney, and Kuwait City.
- Limited the default sensitivity variables to `tas`, `tasmax`, `tasmin`, `huss`, and `sfcWind`; no land weighting is applied automatically to pressure, clouds, radiation, or precipitation.
- Added `src/coastal_sensitivity.py` with strict Amon-grid vs `sftlf`-grid coordinate matching, land-fraction weight renormalization, paired monthly climatologies, per-GCM method differences, and method-effect / inter-GCM-spread diagnostics.
- Retained both raw future-minus-historical changes and the production factor convention (`delta` for temperature; `ratio` for `huss` and wind), avoiding the RH-vs-specific-humidity conflation.
- Added a 0.2 C temperature difference **review trigger** as a predeclared engineering screen only; final method choice remains conditional on downstream EPW/EnergyPlus/SET sensitivity.
- Added `01c_fgoals_madrid_landmask_qa.py` plus a native-grid neighborhood extractor to independently inspect the anomalous FGOALS-g3 Madrid `sftlf` pattern.
- Added city-level resumable caching and GCS→AWS fallback to Stage 02b; the main Stage 02 and all EPW morphing methods remain unchanged.
- Added completeness assertions for the full coastal sensitivity matrix and regression tests for weight renormalization, grid mismatch rejection, paired climatologies, factor construction, GCM-spread comparison, decision screening, and Madrid support-cell QA.

## v1.4.0 — 2026-09-13

- Added `01b_check_land_fraction.py`, an explicit model-specific `sftlf` diagnostic for all 5 GCMs × 8 cities before future-EPW production.
- Added `bilinear_support_table()` so the diagnostic reports the exact four rectilinear support cells and weights used by the existing bilinear extraction, including periodic Greenwich-seam handling.
- Added `src/land_fraction.py` to report support-cell `sftlf (%)`, effective land fraction, effective ocean fraction, land-/ocean-dominant support-cell counts, and a descriptive `weighted_majority_ocean` flag.
- Stage 01b uses baseline-EPW header coordinates, GCS→AWS provider fallback, isolated subprocesses, and a hard provider/model timeout.
- Added detailed CSV and JSON diagnostic outputs under `outputs/diagnostics/land_fraction/`.
- Kept the production CMIP6 interpolation and all morphing methods unchanged; no automatic land weighting or nearest-land fallback is applied in v1.4.
- Added regression tests for periodic support weights, `sftlf` normalization, effective-land-fraction calculation, unchanged production bilinear extraction, and Stage 01b provider fallback.

## v1.3.0 — 2026-09-13

- Changed Stage 02 checkpoint granularity from whole asset to **asset × city**. Each successful city is atomically cached immediately, so a later city timeout no longer discards earlier city work.
- Changed the hard timeout from one shared 8-city worker to one **provider × city** worker (default 300 s).
- Added provider affinity within each asset: after GCS falls back successfully to AWS, the remaining cities for that asset try AWS first instead of repeatedly waiting for GCS timeouts.
- Added explicit process isolation and cleanup for every city read (`Dataset.close()` + worker-process exit), preventing repeated cloud retries from accumulating remote SSL/Zarr resources in one long-lived worker.
- Added lazy time restriction before spatial extraction: historical assets are restricted to 1985–2014; scenario assets are restricted to 2030–2070 before city grid cells are read.
- Added `cache/cmip6_monthly_city/` for fine-grained checkpoints while preserving the existing `cache/cmip6_monthly/*.csv` asset schema consumed by Stages 03–05.
- Preserved compatibility with completed v1.1/v1.2 asset caches.
- Extended `--status` to report both complete asset caches and partial city checkpoints.
- Added regression tests proving that completed cities survive a later-city failure and are skipped after restart.

## v1.2.0 — 2026-09-13

- Added automatic cloud-provider fallback for Stage 02: GCS primary, public AWS `cmip6-pds` mirror secondary.
- Added `s3fs` to the reproducible environment and Stage 00 remote dependency audit.
- Reduced rectilinear remote spatial access to the two latitude × two longitude support coordinates required for bilinear interpolation; interpolation mathematics and extraction labels remain compatible with v1.1.
- Preserved periodic Greenwich seam handling using local wrapped support coordinates rather than concatenating a global cyclic field.
- Added live worker diagnostics for provider open, metadata open, per-city start/done, and asset completion.
- Preserved v1.1 cache filenames/schema so already completed assets remain reusable.
- Added regression tests for AWS mirror mapping, provider fallback, 2×2 support-window extraction, and live city progress callbacks.

## v1.1.0 — 2026-09-13

- Fixed rectilinear bilinear extraction at periodic longitude seams (0/360° and −180/180°) by adding cyclic longitude columns for global grids.
- Added a regression test reproducing the London/Greenwich seam failure that previously produced NaN climatologies for ACCESS-CM2.
- Added model / experiment / variable / city context to Stage 02 extraction errors.
- Added `numexpr>=2.10.2` to the reproducible environment to remove the pandas compatibility warning observed in the Windows Anaconda run.
- Preserved the asset-first cache / retry / hard-timeout architecture and all scientific morphing methods.

## v1.0.0 — 2026-09-13

- Replaced the one-click two-city prototype with a six-stage publication-oriented workflow.
- Expanded frozen CMIP6 manifest to historical + SSP126 + SSP245 + SSP370: 200 Amon assets.
- Added all eight TMYx 2009–2023 baseline stations.
- Changed remote extraction from city-first to asset-first: one Zarr open serves all active cities.
- Added per-asset atomic cache, resume, bounded retries, and subprocess hard timeout.
- Separated remote extraction from offline climate-factor construction and EPW morphing.
- Preserved validated BTWS/BWS/additive-rlds scientific transformations and psl treatment.
- Added final post-serialization target-vs-achieved audit and reproducibility metadata.

## v1.5.1 orchestration extension used by Future EPW Generator v0.9.2
- Added optional validated model/experiment/period selectors to Stage 01 manifest construction.
- Added optional validated model/scenario/target-label selectors to Stage 03 factor construction.
- Existing default invocation remains the original full Protocol R1 workflow.
- Morphing equations and variable-specific transformations are unchanged.
