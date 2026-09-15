# Arbitrary City Workflow Implementation Plan

**Goal:** Allow any valid 8760-hour baseline EPW to define a target city/location and run the validated Stage 00–05 CMIP6→future-EPW workflow without requiring one of the original eight WMO stations.

**Architecture:** Project setup stores an explicit location specification (city label, EPW coordinates, WMO/station metadata, exact baseline path). Stage 00, Stage 02 and Stage 04 consume that specification instead of consulting the frozen eight-city registry. CMIP6 cache paths are namespaced by location identity so a new city starts at 0/200 and cannot be falsely marked complete by another city's cache.

**Tech Stack:** Python, PySide6, pandas/xarray CMIP6 workflow, pytest.

**Constraints:** Preserve the validated R1 scientific protocol; keep EPW coordinates as the default extraction point; retain GCS→AWS fallback and resumable city-level checkpoints; preserve backward-compatible eight-city CLI behavior when no location spec is supplied.
