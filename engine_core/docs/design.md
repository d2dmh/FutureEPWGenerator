# Reproducible CMIP6-to-EPW workflow design

## Goal
Convert eight 2009–2023 TMYx baseline EPWs into 2040 and 2060 future EPWs under SSP1-2.6, SSP2-4.5, and SSP3-7.0 using a frozen five-model CMIP6 ensemble and the validated BTWS/BWS morphing method.

## Frozen scientific design
- Historical CMIP6 reference: 1985–2014, historical experiment only.
- Future windows: 2030–2050 (label 2040) and 2050–2070 (label 2060), both 21-year centered climatological windows.
- Scenarios: ssp126, ssp245, ssp370.
- GCM/member/grid: ACCESS-CM2 r1i1p1f1 gn; GFDL-ESM4 r1i1p1f1 gr1; MPI-ESM1-2-HR r1i1p1f1 gn; IPSL-CM6A-LR r1i1p1f1 gr; FGOALS-g3 r2i1p1f1 gn.
- Amon variables: tas, tasmax, tasmin, huss, psl, sfcWind, clt, rsds, rlds, pr.
- psl is retained intentionally and its anomaly is applied additively to EPW station pressure in Pa.
- Temperature uses BTWS; total sky cover and GHI use BWS; DNI/DHI preserve source partition through the morphed GHI ratio; rlds is additive; huss/wind/pr use ratios; Nopaque is preserved.

## Architecture
The workflow is split into six explicit stages. Each stage writes inspectable intermediate files and can be rerun independently.

1. `00_check_environment.py` — local environment and baseline EPW validation.
2. `01_prepare_manifest.py` — freeze/audit exact CMIP6 Zarr assets and provenance.
3. `02_extract_cmip6.py` — open each remote Zarr asset once, extract all active cities, cache monthly climatologies per asset, retry/time out safely, and resume from completed cache files.
4. `03_build_climate_factors.py` — build per-GCM and ensemble monthly morphing factors entirely offline.
5. `04_generate_future_epw.py` — generate model-specific and ensemble-mean EPWs entirely offline from baseline EPWs + climate factors.
6. `05_validate_outputs.py` — audit 8760-hour structure, physical ranges, hashes, and target-vs-achieved factors after EPW serialization.

## Reproducibility principles
- Exact asset manifest is frozen in CSV and includes zstore/version/member/grid.
- Baseline EPWs are identified by WMO and SHA-256.
- Remote extraction is cached one asset at a time; a valid cache is never re-read from the cloud.
- One asset is opened once and all cities are extracted while it is open.
- Network failures do not silently change interpolation or model selection.
- Every generated EPW is accompanied by an audit CSV and provenance record.
- The repository does not require redistributing the full ~80 MB Pangeo catalog; a frozen 205-asset subset is sufficient for ordinary reproduction.
