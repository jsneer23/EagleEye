from collections.abc import Iterator
from dataclasses import dataclass

from eagleeye.analysis.util import Context, Feature, FeatureResult, Intervals
from eagleeye.config.models import CameraSignals
from eagleeye.errors import NotApplicableError
from eagleeye.signals import BoolSignal

from .enabled import ROBOT_PHASES


def camera_down(samples: Iterator[tuple[int, bool]], match_end_us: int) -> tuple[bool, int, int]:

    total_down_us = 0
    longest_down_us = 0
    down_ts_us: int | None = None

    for ts_us, up in samples:
        if not up:
            down_ts_us = ts_us
        if up and down_ts_us is not None:
            time_down_us = ts_us - down_ts_us
            down_ts_us = None

            total_down_us += time_down_us
            longest_down_us = max(longest_down_us, time_down_us)

    if down_ts_us:
        time_down_us = match_end_us - down_ts_us
        down_ts_us = None

        total_down_us += time_down_us
        longest_down_us = max(longest_down_us, time_down_us)

    return total_down_us != 0, total_down_us, longest_down_us


def down_intervals(samples: Iterator[tuple[int, bool]]) -> Intervals: ...


@dataclass(frozen=True)
class CameraAvailability(FeatureResult):
    down_intervals: Intervals

    @property
    def down(self) -> bool: ...
    @property
    def total_down_us(self) -> int: ...
    @property
    def longest_down_us(self) -> int: ...
    @property
    def up_intervals(self) -> Intervals: ...
    @property
    def pct_down(self) -> float: ...

    def is_down(self, t_us: int) -> bool: ...
    def __rich__(self) -> str: ...


class CameraHealth(Feature[CameraSignals, CameraAvailability]):
    id = "camera_health"
    source = "cameras"

    def compute(self, ctx: Context) -> CameraAvailability:

        signal = ctx.require(self.signals.health_signal, BoolSignal)
        match_span = ctx.feature(ROBOT_PHASES).match_span

        if match_span is None:
            raise NotApplicableError("no enabled period in log")

        camera_zip = signal.zip_between_ts(*match_span)
        down = down_intervals(camera_zip)

        return CameraAvailability(down)


CAMERA_HEALTH = CameraHealth
