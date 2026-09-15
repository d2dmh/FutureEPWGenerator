from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_SCENARIOS = ["ssp126", "ssp245", "ssp370"]
DEFAULT_PERIODS = ["2040", "2060"]
DEFAULT_GCMS = [
    "ACCESS-CM2",
    "GFDL-ESM4",
    "MPI-ESM1-2-HR",
    "IPSL-CM6A-LR",
    "FGOALS-g3",
]


@dataclass
class WorkflowState:
    project_name: str = "Singapore_Future_EPW"
    project_root: str = ""
    baseline_source: str = ""
    city_name: str = "Singapore"
    station_name: str = "Singapore–Changi Intl AP"
    wmo: str = "486980"
    latitude: float = 1.3678
    longitude: float = 103.9826
    elevation: float = 6.7
    baseline_hours: int = 8760
    cities: list[str] = field(default_factory=lambda: ["Singapore"])
    scenarios: list[str] = field(default_factory=lambda: DEFAULT_SCENARIOS.copy())
    periods: list[str] = field(default_factory=lambda: DEFAULT_PERIODS.copy())
    gcms: list[str] = field(default_factory=lambda: DEFAULT_GCMS.copy())
    climate_mode: str = "reproducible"
    cmip6_total: int = 200
    cmip6_complete: int = 0
    cmip6_failed: int = 0
    city_cached: int = 0
    remote_ready: int = 0
    cmip6_running: bool = False
    active_provider: str = "GCS"
    gcs_status: str = "Primary"
    aws_status: str = "Standby"
    recent_activity: list[str] = field(default_factory=list)
    factors_ready: bool = False
    fallback_rows: int = 0
    generation_complete: int = 0
    validation_passed: bool | None = None
    audit_groups: int = 0
    last_error: str = ""

    def pause_cmip6(self) -> None:
        self.cmip6_running = False

    def resume_cmip6(self) -> None:
        self.cmip6_running = True

    def advance_cmip6(self) -> None:
        # Retained for the self-test and backward compatibility. Real progress
        # is synchronized from the project workspace in functional MVP.
        if not self.cmip6_running or self.cmip6_complete >= self.cmip6_total:
            return
        self.cmip6_complete += 1

    def trigger_provider_fallback(self) -> None:
        self.active_provider = "AWS"
        self.gcs_status = "Timeout"
        self.aws_status = "Active fallback"
        self.recent_activity.insert(0, "GCS timeout → AWS fallback activated")


def dynamic_asset_total(state: WorkflowState) -> int:
    if state.climate_mode != "advanced":
        return len(DEFAULT_GCMS) * (1 + len(DEFAULT_SCENARIOS)) * 10
    return len(state.gcms) * (1 + len(state.scenarios)) * 10


def expected_epw_count(state: WorkflowState) -> int:
    return len(state.cities) * len(state.scenarios) * len(state.periods) * (len(state.gcms) + 1)


def configuration_fingerprint(state: WorkflowState) -> str:
    scenarios = "_".join(s.upper().replace("SSP", "") for s in state.scenarios)
    periods = "_".join(state.periods)
    return f"EPW-R1-1985_2014-SSP{scenarios}-{periods}-{len(state.gcms)}GCM"


def validation_overall_status(*, hard_checks_pass: bool, warning_count: int) -> str:
    if not hard_checks_pass:
        return "FAIL"
    if warning_count > 0:
        return "PASS WITH WARNINGS"
    return "PASS"
