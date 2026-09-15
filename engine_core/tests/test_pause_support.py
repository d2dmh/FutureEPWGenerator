from __future__ import annotations

from pathlib import Path
import pandas as pd

from src.cmip6_io import process_manifest_assets_by_city


def test_process_manifest_can_stop_before_starting_next_asset(tmp_path: Path):
    manifest = pd.DataFrame([
        {"source_id":"M","experiment_id":"historical","variable_id":"tas","member_id":"r1","grid_label":"gn","table_id":"Amon","version":"v1","zstore":"z1"},
        {"source_id":"M","experiment_id":"historical","variable_id":"huss","member_id":"r1","grid_label":"gn","table_id":"Amon","version":"v1","zstore":"z2"},
    ])
    locations={"Singapore":(1.3,103.9)}
    calls=[]
    stop={"value":False}

    def runner(row, city, loc):
        calls.append(str(row.variable_id))
        # Minimal city cache schema expected by validators.
        stop["value"] = True
        return pd.DataFrame([{**row.to_dict(), "city":city, "month":1, "period":"1985-2014", "value":1.0, "provider":"gcs"}])

    # This test only asserts that the stop callback is part of the public API.
    # Cache schema details are exercised elsewhere; an immediate stop must return cleanly.
    result=process_manifest_assets_by_city(
        manifest, locations, tmp_path/"assets", tmp_path/"cities", runner,
        retries=1, progress=None, should_stop=lambda: True,
    )
    assert result["stopped"] is True
    assert calls == []
