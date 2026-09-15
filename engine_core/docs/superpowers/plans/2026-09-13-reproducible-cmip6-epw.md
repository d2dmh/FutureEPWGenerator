# Reproducible CMIP6-to-EPW Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Build a publication-ready six-stage Python workflow that reproduces eight-city future EPWs from frozen CMIP6 assets with resumable one-open-per-asset extraction and explicit validation.

**Architecture:** Separate remote CMIP6 I/O from offline factor construction and EPW morphing. Keep the validated scientific transformations unchanged while replacing city-first remote reads with asset-first extraction, persistent per-asset cache files, bounded retries, and provenance outputs.

**Tech Stack:** Python 3.10+, numpy, pandas, xarray, scipy, zarr<3, gcsfs, cftime, fsspec, pytest.

**Spec:** `docs/design.md`

## Global Constraints
- Historical reference is 1985–2014 historical only.
- Future windows are 2030–2050 -> 2040 and 2050–2070 -> 2060.
- Scenarios are ssp126, ssp245, ssp370.
- Use the frozen five model/member/grid combinations in `config.py`.
- Use exactly ten Amon variables: tas, tasmax, tasmin, huss, psl, sfcWind, clt, rsds, rlds, pr.
- Do not replace psl with ps.
- Do not change the validated BTWS/BWS/rlds scientific morphing logic.
- A valid cache must be resumable and tied to exact zstore/version/city/window metadata.
- Each remote Zarr asset must be opened at most once per uncached extraction attempt, regardless of city count.

---

### Task 1: Project configuration, catalog selection, and case matrix

**Files:**
- Create: `config.py`
- Create: `src/catalog.py`
- Create: `src/workflow.py`
- Test: `tests/test_catalog_workflow.py`

**Interfaces:**
- `select_main_manifest(catalog, experiments) -> DataFrame`
- `select_sftlf_manifest(catalog) -> DataFrame`
- `build_case_matrix(cities=None) -> DataFrame`

- [x] Write tests for exact 200-asset manifest selection, five sftlf assets, and 288 full output cases.
- [x] Run tests and verify RED because modules are absent.
- [x] Implement minimal configuration/catalog/workflow code.
- [x] Run tests and verify GREEN.

### Task 2: EPW I/O and scientific morphing preservation

**Files:**
- Create: `src/morphing.py`
- Create: `src/epw.py`
- Test: `tests/test_epw_morphing.py`

**Interfaces:**
- `read_epw`, `epw_to_morph_base`, `write_morphed_epw`
- `morph(base, signal)`
- `generate_future_epw(...) -> dict`

- [x] Port zero-signal and synthetic-signal tests before production files exist.
- [x] Verify RED.
- [x] Implement by preserving the validated v5.2 scientific formulas and EPW field mappings.
- [x] Verify GREEN, including exact zero-signal identity before serialization.

### Task 3: Asset-first CMIP6 extraction, cache, retry, and timeout

**Files:**
- Create: `src/cmip6_io.py`
- Test: `tests/test_cmip6_io.py`

**Interfaces:**
- `extract_point_series(...)`
- `monthly_climatology_from_series(...)`
- `extract_asset_for_cities(...)`
- `cache_is_valid(...)`
- `process_manifest_assets(...)`

- [x] Write tests proving one asset runner call serves multiple cities, cache skip/resume works, units are enforced, and timeout/retry errors are surfaced.
- [x] Verify RED.
- [x] Implement asset-first extraction and atomic cache writes.
- [x] Verify GREEN.

### Task 4: Climate factors and ensemble summaries

**Files:**
- Create: `src/factors.py`
- Test: `tests/test_factors.py`

**Interfaces:**
- `build_factors(climatology) -> DataFrame`
- `ensemble_summary(per_gcm) -> DataFrame`
- `signal_dict_from_factor_table(...) -> dict`

- [x] Write delta/ratio tests for all ten signals and all scenarios/windows.
- [x] Verify RED.
- [x] Implement factor builder from cached long climatology records.
- [x] Verify GREEN.

### Task 5: Six public entry-point scripts and validation outputs

**Files:**
- Create: `00_check_environment.py`
- Create: `01_prepare_manifest.py`
- Create: `02_extract_cmip6.py`
- Create: `03_build_climate_factors.py`
- Create: `04_generate_future_epw.py`
- Create: `05_validate_outputs.py`
- Create: `src/validation.py`
- Test: `tests/test_cli_stages.py`

**Interfaces:**
- Every script exposes `main(argv=None) -> int`.
- Stages write JSON/CSV provenance and return non-zero on validation failure.

- [x] Write CLI tests for offline stages using synthetic data.
- [x] Verify RED.
- [x] Implement the six scripts and validation module.
- [x] Verify GREEN.

### Task 6: Frozen inputs, documentation, and full offline verification

**Files:**
- Create: `requirements.txt`
- Create: `README.md`
- Create: `CITATION.cff`
- Create: `inputs/catalog/catalog_subset_205_assets.csv`
- Create: `inputs/catalog/manifest_metadata.json`
- Populate: `inputs/baseline_epw/` with the eight working TMYx files for the research package.

- [x] Generate/audit the frozen 205-asset subset from the 81 MB Pangeo catalog.
- [x] Run `00_check_environment.py` against all eight EPWs.
- [x] Run `01_prepare_manifest.py` and verify 200 Amon + 5 sftlf assets.
- [x] Run the entire pytest suite.
- [x] Run Python compilation on all `.py` files.
- [x] Package the repository as a ZIP and record final verification evidence.
