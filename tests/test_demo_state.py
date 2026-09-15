from future_epw_demo.demo_state import (
    WorkflowState,
    configuration_fingerprint,
    expected_epw_count,
    validation_overall_status,
)


def test_default_single_city_expected_epw_count_is_36():
    state = WorkflowState()
    assert expected_epw_count(state) == 36


def test_expected_epw_count_updates_with_selections():
    state = WorkflowState(
        cities=["Singapore", "Beijing"],
        scenarios=["ssp126", "ssp245"],
        periods=["2040"],
        gcms=["ACCESS-CM2", "GFDL-ESM4"],
    )
    assert expected_epw_count(state) == 12


def test_configuration_fingerprint_matches_recommended_defaults():
    state = WorkflowState()
    assert configuration_fingerprint(state) == "EPW-R1-1985_2014-SSP126_245_370-2040_2060-5GCM"


def test_validation_with_scientific_warning_is_passed_with_warnings():
    assert validation_overall_status(hard_checks_pass=True, warning_count=6) == "PASS WITH WARNINGS"
    assert validation_overall_status(hard_checks_pass=True, warning_count=0) == "PASS"
    assert validation_overall_status(hard_checks_pass=False, warning_count=0) == "FAIL"


def test_cmip6_progress_respects_pause_and_resume():
    state = WorkflowState()
    state.cmip6_complete = 163
    state.pause_cmip6()
    state.advance_cmip6()
    assert state.cmip6_complete == 163
    state.resume_cmip6()
    state.advance_cmip6()
    assert state.cmip6_complete == 164


def test_provider_fallback_switches_to_aws_and_records_warning():
    state = WorkflowState()
    state.trigger_provider_fallback()
    assert state.active_provider == "AWS"
    assert state.gcs_status == "Timeout"
    assert state.aws_status == "Active fallback"
    assert any("GCS timeout" in item for item in state.recent_activity)
