from __future__ import annotations

from dataclasses import dataclass
from statistics import median
import time


@dataclass(frozen=True)
class ETAEstimate:
    ready: bool
    seconds_per_asset: float | None = None
    remaining_seconds: float | None = None
    sample_count: int = 0


class ExtractionETA:
    """Runtime-only ETA model for genuine remote Stage-02 extractions."""

    def __init__(self):
        self.provider: str | None = None
        self.samples: list[float] = []
        self._active: dict[str, tuple[str, float]] = {}
        self._paused = False
        self._frozen: ETAEstimate | None = None

    def start_asset(self, asset_id: str, provider: str, *, started_at: float | None = None) -> None:
        now = time.monotonic() if started_at is None else float(started_at)
        if self.provider is None:
            self.provider = provider
        elif provider != self.provider:
            self.change_provider(provider, changed_at=now)
        self._active[asset_id] = (provider, now)

    def finish_asset(
        self,
        asset_id: str,
        provider: str,
        *,
        finished_at: float | None = None,
        genuine_remote: bool = True,
    ) -> None:
        now = time.monotonic() if finished_at is None else float(finished_at)
        started = self._active.pop(asset_id, None)
        if provider != self.provider:
            self.change_provider(provider, changed_at=now)
        if not genuine_remote or started is None:
            return
        started_provider, started_at = started
        if started_provider != provider:
            return
        duration = max(0.0, now - started_at)
        if duration <= 0:
            return
        self.samples.append(duration)
        self.samples = self.samples[-8:]

    def change_provider(self, provider: str, *, changed_at: float | None = None) -> None:
        if provider == self.provider:
            return
        now = time.monotonic() if changed_at is None else float(changed_at)
        self.provider = provider
        self.samples.clear()
        # An in-flight asset that falls back to another provider should be timed
        # from the switch, not from the failed provider's start time.
        self._active = {asset: (provider, now) for asset in self._active}
        self._frozen = None

    def estimate(self, remaining_remote: int) -> ETAEstimate:
        if self._paused and self._frozen is not None:
            return self._frozen
        if len(self.samples) < 3:
            return ETAEstimate(False, sample_count=len(self.samples))
        typical = float(median(self.samples[-8:]))
        remaining = max(0, int(remaining_remote))
        return ETAEstimate(
            True,
            seconds_per_asset=typical,
            remaining_seconds=typical * remaining,
            sample_count=len(self.samples),
        )

    def pause(self, *, remaining_remote: int) -> None:
        self._frozen = self.estimate(remaining_remote)
        self._paused = True

    def resume(self) -> None:
        self._paused = False
        self._frozen = None
        self.samples.clear()
        self._active.clear()


def format_duration(seconds: float | int | None, *, language: str = "en") -> str:
    if seconds is None:
        return "—"
    seconds = max(0, int(round(float(seconds))))
    zh = language == "zh_CN"
    if seconds < 60:
        return f"{seconds} 秒" if zh else f"{seconds} s"
    if seconds < 3600:
        minutes, secs = divmod(seconds, 60)
        if zh:
            return f"{minutes} 分" if secs == 0 else f"{minutes} 分 {secs} 秒"
        return f"{minutes} min" if secs == 0 else f"{minutes} min {secs} s"
    hours, rem = divmod(seconds, 3600)
    minutes = rem // 60
    if zh:
        return f"{hours} 小时" if minutes == 0 else f"{hours} 小时 {minutes} 分"
    return f"{hours} h" if minutes == 0 else f"{hours} h {minutes} min"
