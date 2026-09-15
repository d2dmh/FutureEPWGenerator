from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PreflightCheck:
    name: str
    passed: bool
    detail: str
    blocking: bool = True
    recovery: str = ""
    key: str = ""


@dataclass(frozen=True)
class PreflightReport:
    checks: tuple[PreflightCheck, ...]

    @property
    def passed(self) -> bool:
        return all(check.passed or not check.blocking for check in self.checks)

    def as_dict(self) -> dict[str, PreflightCheck]:
        return {check.name: check for check in self.checks}

    def failed_checks(self) -> tuple[PreflightCheck, ...]:
        return tuple(check for check in self.checks if check.blocking and not check.passed)


def run_generation_preflight(ws, *, process_active: bool = False) -> PreflightReport:
    snap = ws.status_snapshot()
    project_ok = ws.project_file.is_file()
    baseline_ok = ws.baseline_path.is_file() and ws.verify_baseline_fingerprint()
    location_ok = ws.location_spec_file.is_file() and ws.location_spec_matches_project()
    protocol_ok = ws.project_protocol() == "R1"
    selection_ok = bool(ws.effective_gcms() and ws.effective_scenarios() and ws.effective_periods())
    expected_assets = ws.dynamic_asset_total()
    manifest_count = ws.manifest_row_count()
    manifest_ok = ws.manifest_matches_selection()
    cache_ok = snap.cmip6_total == expected_assets and snap.cmip6_complete == expected_assets and snap.cmip6_missing == 0
    output_ok = ws.ensure_output_dirs_writable()
    idle_ok = not process_active

    checks = (
        PreflightCheck("Project", project_ok, "project.json found" if project_ok else "project.json missing", recovery="Open or save a valid Future EPW project.", key="project"),
        PreflightCheck("Baseline EPW", baseline_ok, "fingerprint matches" if baseline_ok else "missing or fingerprint mismatch", recovery="Restore the original baseline EPW or create a new project.", key="baseline"),
        PreflightCheck("Location", location_ok, "location specification matches project" if location_ok else "location specification is missing or stale", recovery="Reopen the project to regenerate its location specification.", key="location"),
        PreflightCheck("Protocol R1", protocol_ok, f"workflow protocol: {ws.project_protocol() or 'missing'}", recovery="Use a project created with Protocol R1.", key="protocol"),
        PreflightCheck(
            "Climate selection", selection_ok,
            f"{len(ws.effective_gcms())} GCM / {len(ws.effective_scenarios())} SSP / {len(ws.effective_periods())} period",
            recovery="Select at least one validated GCM, SSP pathway, and future period.", key="selection",
        ),
        PreflightCheck("Manifest", manifest_ok, f"{manifest_count}/{expected_assets} Stage-02 assets", recovery="Run Stage 01 to rebuild the manifest for the current climate selection.", key="manifest"),
        PreflightCheck("CMIP6 cache", cache_ok, f"{snap.cmip6_complete}/{snap.cmip6_total}", recovery=f"Resume CMIP6 extraction until the active location reaches {expected_assets}/{expected_assets}.", key="cache"),
        PreflightCheck("Output directory", output_ok, "writable" if output_ok else "not writable", recovery="Choose a writable project directory or fix file permissions.", key="output"),
        PreflightCheck("Workflow idle", idle_ok, "idle" if idle_ok else "another workflow process is running", recovery="Wait for the active workflow process to finish or pause safely.", key="idle"),
    )
    return PreflightReport(checks)
