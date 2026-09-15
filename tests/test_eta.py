from __future__ import annotations

from future_epw_demo.eta import ExtractionETA, format_duration


def finish(eta: ExtractionETA, asset: str, provider: str, start: float, duration: float, *, genuine=True):
    eta.start_asset(asset, provider, started_at=start)
    eta.finish_asset(asset, provider, finished_at=start + duration, genuine_remote=genuine)


def test_eta_requires_three_genuine_remote_samples():
    eta = ExtractionETA()
    finish(eta, "a", "GCS", 0, 10)
    finish(eta, "b", "GCS", 20, 20)
    assert eta.estimate(10).ready is False
    finish(eta, "c", "GCS", 50, 30)
    estimate = eta.estimate(10)
    assert estimate.ready is True
    assert estimate.seconds_per_asset == 20
    assert estimate.remaining_seconds == 200


def test_eta_uses_median_of_latest_eight_and_ignores_cache_hits():
    eta = ExtractionETA()
    for i, duration in enumerate([1, 2, 3, 4, 5, 6, 7, 8, 100]):
        finish(eta, str(i), "GCS", i * 200.0, duration)
    finish(eta, "cached", "GCS", 5000, 999, genuine=False)
    # Latest 8 are 2..8,100 => median=(5+6)/2=5.5
    estimate = eta.estimate(4)
    assert estimate.ready is True
    assert estimate.seconds_per_asset == 5.5
    assert estimate.remaining_seconds == 22


def test_provider_change_resets_samples():
    eta = ExtractionETA()
    for i in range(3):
        finish(eta, f"g{i}", "GCS", i * 10.0, 5)
    assert eta.estimate(10).ready is True
    eta.change_provider("AWS", changed_at=100)
    assert eta.estimate(10).ready is False
    for i in range(3):
        finish(eta, f"a{i}", "AWS", 110 + i * 10.0, 2)
    assert eta.estimate(10).seconds_per_asset == 2


def test_pause_freezes_eta_and_resume_restarts_sampling():
    eta = ExtractionETA()
    for i in range(3):
        finish(eta, str(i), "GCS", i * 20.0, 10)
    eta.pause(remaining_remote=5)
    frozen = eta.estimate(99)
    assert frozen.ready is True
    assert frozen.remaining_seconds == 50
    eta.resume()
    assert eta.estimate(5).ready is False


def test_human_duration_formatting():
    assert format_duration(42) == "42 s"
    assert format_duration(90) == "1 min 30 s"
    assert format_duration(3720) == "1 h 2 min"


def test_human_duration_formatting_supports_chinese_ui():
    assert format_duration(42, language="zh_CN") == "42 秒"
    assert format_duration(90, language="zh_CN") == "1 分 30 秒"
    assert format_duration(3720, language="zh_CN") == "1 小时 2 分"
