# Future EPW Generator Functional Backend Integration Plan

**Goal:** Convert the v0.5 mock UI into a functional single-city research application that runs the validated CMIP6→EPW workflow for the eight frozen station cities.

**Architecture:** Keep the v0.5 PySide6 UI. Bundle the validated v1.5.1 workflow under `engine_core/` and run stages 00–05 as subprocesses using the same Python interpreter as the GUI. Project workspaces preserve the original CLI directory layout (`inputs/`, `cache/`, `outputs/`) so existing command-line runs can be reused.

**Tech Stack:** Python 3.12+, PySide6, pandas/xarray/scipy/fsspec/zarr/gcsfs/s3fs/cftime.

## Global Constraints
- UI baseline remains v0.5.
- Scientific configuration remains Protocol R1: 5 GCMs, SSP126/245/370, 1985–2014 historical, 2040/2060 windows.
- Stage 03 includes the precipitation dry-baseline fallback hotfix v1.5.1.
- No sftlf/coastal-sensitivity workflow in production path.
- Real work runs in background processes; GUI must stay responsive.
- Project workspace must be reusable by the original CLI scripts.

## Tasks
1. Add project workspace model, EPW header parser, persistence, and status inference.
2. Bundle the validated workflow core and apply v1.5.1 hotfix.
3. Add command builder and process runner for stages 00–05.
4. Wire Project Setup to real EPW import and project creation.
5. Wire CMIP6 page to real prepare/status/start/pause/resume logging.
6. Wire Generate page to real Stage 03→04 sequence.
7. Wire Validation page to real Stage 05 results and file actions.
8. Update dependencies, README, tests, and package.
