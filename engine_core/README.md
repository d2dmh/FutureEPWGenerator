# Reproducible CMIP6 → Future EPW Workflow

This repository converts eight **TMYx 2009–2023** baseline EPW weather files into future EPWs for **2040** and **2060** under **SSP1-2.6, SSP2-4.5, and SSP3-7.0** using a frozen five-model CMIP6 ensemble.

The workflow is intentionally split into six production stages plus three explicit diagnostics/sensitivity stages (`01b`, `01c`, and `02b`). It is not a one-click runner: every stage produces inspectable intermediate files for reproducibility, peer review, and Supplementary Methods.

## Scientific configuration

- Historical CMIP6 reference: **1985–2014**, historical experiment only.
- Future windows: **2030–2050 → 2040** and **2050–2070 → 2060** (21-year centered climatologies).
- Scenarios: `ssp126`, `ssp245`, `ssp370`.
- Models:
  - ACCESS-CM2 — `r1i1p1f1`, `gn`
  - GFDL-ESM4 — `r1i1p1f1`, `gr1`
  - MPI-ESM1-2-HR — `r1i1p1f1`, `gn`
  - IPSL-CM6A-LR — `r1i1p1f1`, `gr`
  - FGOALS-g3 — `r2i1p1f1`, `gn`
- Amon variables: `tas, tasmax, tasmin, huss, psl, sfcWind, clt, rsds, rlds, pr`.
- `psl` is intentional. Its monthly anomaly is applied additively to EPW station pressure in **Pa**.
- Temperature uses BTWS; GHI/total sky cover use BWS; DNI/DHI preserve the source EPW partition by the morphed-GHI ratio; `rlds` is additive; `huss`, wind, and precipitation use ratios; opaque sky cover is preserved.

## Why Stage 02 uses city-level checkpoints

The first public prototype used one subprocess for all eight cities in an asset. Real cloud tests showed a failure mode: seven cities could finish successfully, but if the eighth city exceeded the 300 s asset timeout, the whole subprocess was killed and all seven successful reads had to be repeated. Repeated GCS/AWS retries could also accumulate enough remote I/O pressure to trigger SSL-layer `MemoryError` failures on Windows.

v1.3+ therefore keeps the **asset-first outer loop** but makes the checkpoint and timeout unit **asset × city**:

```text
ACCESS-CM2 / ssp126 / huss
  Delhi       -> read -> save city cache immediately
  Singapore   -> read -> save city cache immediately
  Kuwait City -> read -> save city cache immediately
  ...
  Toronto     -> timeout/failure

restart Stage 02
  Delhi       -> cached, skip
  Singapore   -> cached, skip
  Kuwait City -> cached, skip
  ...
  Toronto     -> retry only this city
```

Each **provider × city** read runs in its own short-lived subprocess with a hard timeout (default 300 s). Google Cloud Storage is tried first. If it fails or times out, the public AWS `cmip6-pds` mirror is tried. When AWS successfully rescues a city after a GCS timeout, AWS is promoted to first choice for the remaining cities of that asset, avoiding repeated five-minute GCS waits.

Every city result is atomically written to `cache/cmip6_monthly_city/`. When all requested cities for an asset are present and valid, Stage 02 merges them into the unchanged asset cache in `cache/cmip6_monthly/`. Stages 03–05 therefore keep the same input schema as v1.1/v1.2. Fully completed v1.1/v1.2/v1.3 asset caches can be copied directly into the v1.5 `cache/cmip6_monthly/` directory and are reused.

Before spatial data access, Stage 02 lazily restricts time to the required experiment window: **1985–2014** for historical and **2030–2070** for scenario assets. For rectilinear grids it then identifies only the **two latitude × two longitude support coordinates** required for bilinear interpolation. Global 0–360° grids explicitly wrap the Greenwich seam, so sites such as London interpolate between the final longitude column and the periodic 360/0° column rather than becoming out of bounds. The method does not silently fall back to nearest-neighbour extraction.

## Repository structure

```text
00_check_environment.py
01_prepare_manifest.py
01b_check_land_fraction.py
01c_fgoals_madrid_landmask_qa.py
02_extract_cmip6.py
02b_coastal_sensitivity.py
03_build_climate_factors.py
04_generate_future_epw.py
05_validate_outputs.py
config.py
src/
inputs/
  baseline_epw/
  baseline_epw_manifest.csv
  catalog/catalog_subset_205_assets.csv
cache/
  cmip6_monthly/       # completed asset caches for Stage 03
  cmip6_monthly_city/  # city-level checkpoints
outputs/
tests/
```

`catalog_subset_205_assets.csv` contains **200 Amon assets + 5 model-specific `sftlf` land-fraction assets** selected from the full Pangeo CMIP6 catalog. Ordinary reproduction does not require committing the full ~80 MB catalog.

## Install

Recommended tested environment: Python 3.13.x.

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

macOS/Linux:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Run the six stages

### 00 — Environment + baseline EPW audit

```bash
python 00_check_environment.py
```

Checks package availability, a 2-D xarray/SciPy interpolation smoke test, all eight WMO-linked EPWs, 8760-hour structure, core physical ranges, and SHA-256 provenance.

### 01 — Freeze/audit the CMIP6 manifests

```bash
python 01_prepare_manifest.py
```

Expected outputs in `outputs/manifest/`:

- `manifest_cmip6.csv` — 200 Amon assets
- `manifest_sftlf.csv` — 5 land-fraction assets
- `case_matrix.csv` — 288 final EPW cases
- `manifest_metadata.json`

### 01b — Diagnose coastal/island land fraction before production

```bash
python 01b_check_land_fraction.py --manifest outputs/manifest/manifest_sftlf.csv
```

This stage reads the model-specific fixed field `sftlf` and inspects the **same four rectilinear support cells** used by Stage 02 bilinear interpolation for every model × city pair. It uses the coordinates stored in the baseline EPW headers, so the diagnostic and production extraction target the same points. GCS is tried first and AWS `cmip6-pds` is used as fallback.

Outputs in `outputs/diagnostics/land_fraction/`:

- `land_fraction_support_points.csv` — one row per support cell, including support latitude/longitude, bilinear weight, `sftlf (%)`, and weighted contribution.
- `land_fraction_summary.csv` — one row per model × city with effective land/ocean fraction and support-cell counts.
- `land_fraction_metadata.json` — manifest hash and diagnostic provenance.

The effective land fraction is

```text
L_eff (%) = sum_i [w_i * sftlf_i (%)]
```

where the four `w_i` are the unchanged bilinear weights and sum to one. `weighted_majority_ocean=True` means `L_eff < 50%`; this is a **diagnostic flag only**. v1.5 does **not** automatically switch to land-weighted interpolation or nearest-land extraction. Singapore, Sydney, and Kuwait City are printed first in the console summary for manual review. Any production-method change should be made only after comparing this diagnostic with sensitivity tests.

### 01c — QA the FGOALS-g3 land mask around Madrid

```bash
python 01c_fgoals_madrid_landmask_qa.py
```

This is a separate QA step for the unexpectedly low `sftlf` values found in two FGOALS-g3 support cells around Madrid. It downloads only the FGOALS-g3 fixed land-fraction field, extracts a native-grid neighborhood around the Madrid EPW coordinate, and marks the four cells used by bilinear interpolation. It does **not** alter any production interpolation.

Outputs in `outputs/diagnostics/fgoals_madrid_landmask_qa/`:

- `fgoals_madrid_sftlf_neighborhood.csv` — native-grid neighborhood with coordinates, `sftlf`, distance rank, and support-cell flags.
- `fgoals_madrid_sftlf_matrix.csv` — latitude × longitude matrix for quick visual inspection.
- `fgoals_madrid_bilinear_support.csv` — the four support cells only.
- `fgoals_madrid_landmask_qa_metadata.json` — provenance and the four support-cell values.

### 02 — Extract real CMIP6 monthly climatologies

```bash
python 02_extract_cmip6.py --manifest outputs/manifest/manifest_cmip6.csv
```

Progress is explicit at the asset, city, and provider levels, e.g.:

```text
[12/200] extract ACCESS-CM2 ssp126 huss | city Delhi | attempt 1/3
        provider=gcs: start
        [gcs] opening metadata...
        [gcs] metadata opened
        [gcs] city Delhi: start
```

If GCS times out or fails, Stage 02 tries AWS for **that city**. A successful fallback is promoted for the remaining cities of the same asset:

```text
        provider=gcs: failed: gcs city worker exceeded 300s
        provider=aws: start
        [aws] city Delhi: done
[12/200] extract ACCESS-CM2 ssp126 huss | city Singapore | attempt 1/3
        provider=aws: start
```

If the process is interrupted, run the **same command again**. Valid full assets are skipped, and within a partial asset each valid city checkpoint is skipped.

Useful diagnostics:

```bash
python 02_extract_cmip6.py --manifest outputs/manifest/manifest_cmip6.csv --status
```

Change network protection if necessary:

```bash
python 02_extract_cmip6.py --manifest outputs/manifest/manifest_cmip6.csv --timeout 600 --retries 3
```

Provider order can be controlled explicitly:

```bash
# Default
python 02_extract_cmip6.py --manifest outputs/manifest/manifest_cmip6.csv --providers gcs aws

# Diagnostic: AWS only
python 02_extract_cmip6.py --manifest outputs/manifest/manifest_cmip6.csv --providers aws
```

The final asset-cache schema remains unchanged, so valid v1.1/v1.2/v1.3 `cache/cmip6_monthly/*.csv` files can be copied into the v1.5 asset-cache directory and will be reused. New partial progress is stored separately in `cache/cmip6_monthly_city/`.

### 02b — Coastal interpolation sensitivity test

Run this after `01b`; it is independent of the main Stage 02 output and has its own city-level cache.

```bash
python 02b_coastal_sensitivity.py
```

Default scope is deliberately narrow: **Singapore, Sydney, Kuwait City** and `tas, tasmax, tasmin, huss, sfcWind`. For every model, scenario, period, and month it compares:

1. the unchanged standard four-cell bilinear signal; and
2. a diagnostic land-aware signal where the same bilinear weights are multiplied by `sftlf/100` and renormalized.

The script records both the raw future-minus-historical change for all five variables and the exact factor convention used by the production workflow (`delta` for temperature; `ratio` for `huss` and `sfcWind`). It also compares the method effect with inter-GCM spread. A `0.2 C` temperature difference is recorded only as an **engineering review trigger**, not as a universal scientific threshold. No final method choice is automated. If the weather-level difference is material, the next decision layer is a paired future-EPW → EnergyPlus → SET/discomfort/energy sensitivity run.

Useful commands:

```bash
# See how many city jobs are cached before running
python 02b_coastal_sensitivity.py --status

# Run Singapore first if desired
python 02b_coastal_sensitivity.py --cities Singapore

# Resume after interruption: run the same command again
python 02b_coastal_sensitivity.py
```

Outputs in `outputs/diagnostics/coastal_sensitivity/`:

- `coastal_paired_monthly_climatology.csv`
- `coastal_sensitivity_per_gcm.csv`
- `coastal_sensitivity_monthly_ensemble.csv`
- `coastal_sensitivity_decision_screen.csv`
- `coastal_sensitivity_metadata.json`

### 03 — Build climate-change factors (offline)

```bash
python 03_build_climate_factors.py --manifest outputs/manifest/manifest_cmip6.csv
```

Expected outputs in `outputs/factors/`:

- `monthly_climatology_long.csv`
- `climate_factors_per_gcm.csv`
- `climate_factors_ensemble.csv`
- `factor_metadata.json`

At this point all subsequent steps are offline; CMIP6 does not need to be reread.

### 04 — Generate future EPWs (offline)

```bash
python 04_generate_future_epw.py \
  --per-gcm outputs/factors/climate_factors_per_gcm.csv \
  --ensemble outputs/factors/climate_factors_ensemble.csv
```

Full expected total: **288 EPWs** = 8 cities × 3 SSPs × 2 future periods × (5 GCMs + 1 ensemble mean). This consists of **240 GCM-specific EPWs + 48 ensemble-mean EPWs**.

Every EPW also receives a target-vs-achieved audit CSV after writing and rereading the file.

### 05 — Final validation

```bash
python 05_validate_outputs.py
```

Expected outputs in `outputs/validation/`:

- `validation_summary.csv`
- `target_vs_achieved_summary.csv`
- `validation_metadata.json`

## Tests

```bash
python -m pytest -q
```

The tests cover manifest one-to-one selection, eight-city case construction, ordinary and periodic-longitude bilinear extraction, 2×2 support-window restriction, pre-spatial time slicing, GCS→AWS path mapping and provider fallback, contextual extraction errors, unit checks, whole-asset cache compatibility, city-level partial resume, retry behavior, climate-factor construction, BTWS targets, zero-signal identity, shortwave partition preservation, EPW serialization, and all production stage entry points plus the `01b` land-fraction diagnostic, `01c` Madrid land-mask QA, and `02b` coastal sensitivity logic in offline/synthetic mode.

## Baseline EPW provenance

`inputs/baseline_epw_manifest.csv` records WMO, coordinates, filename, and SHA-256 for all eight TMYx 2009–2023 files. The working research package includes the files for convenience. Before putting third-party EPWs in a public Git repository, verify their redistribution terms; if necessary, publish only the manifest/hashes and instruct users to place the matching station files in `inputs/baseline_epw/`.

## Reproducibility note

The frozen asset manifest is the authoritative data-selection record. Re-running against a later mutable catalog should not silently change the model/member/grid choices. The workflow fails loudly when exact required assets, months, units, or baseline WMO files are missing.
