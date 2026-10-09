from bisect import bisect_right
from collections.abc import Iterator
from dataclasses import dataclass

from eagleeye.analysis.util import Context, Feature, FeatureResult, Interval, Intervals
from eagleeye.analysis.util.check import us_to_s
from eagleeye.config.models import CameraSignals
from eagleeye.errors import LogFormatError, NotApplicableError
from eagleeye.signals import BoolSignal

from .enabled import ROBOT_PHASES


def down_intervals(samples: Iterator[tuple[int, bool]], match_span: Interval) -> Intervals:

    curr_interval_start: int | None = None
    result: Intervals = []

    for ts_us, up in samples:
        if ts_us < match_span[0]:
            continue
        if ts_us > match_span[1]:
            break

        if not up and curr_interval_start is None:
            curr_interval_start = ts_us
        if up:
            if curr_interval_start is None:
                if ts_us >= match_span[0]:
                    curr_interval_start = match_span[0]
                else:
                    raise LogFormatError(
                        "cannot create down intervals - camera health signal is malformed."
                    )

            result.append((curr_interval_start, ts_us))
            curr_interval_start = None
        if not up:
            curr_interval_start = ts_us

    if curr_interval_start is not None and curr_interval_start < match_span[1]:
        result.append((curr_interval_start, match_span[1]))

    return result


@dataclass(frozen=True)
class CameraAvailability(FeatureResult):
    down_intervals: Intervals
    match_span: Interval

    @property
    def down(self) -> bool:
        return len(self.down_intervals) > 0

    @property
    def total_down_us(self) -> int:
        total_us = 0
        for start, end in self.down_intervals:
            total_us += end - start

        return total_us

    @property
    def total_down_s(self) -> float:
        return us_to_s(self.total_down_us)

    @property
    def total_up_us(self) -> int:
        return self.match_span[1] - self.match_span[0] - self.total_down_us

    @property
    def total_up_s(self) -> float:
        return us_to_s(self.total_up_us)

    @property
    def longest_down_s(self) -> float:
        longest_us = 0
        for start, end in self.down_intervals:
            longest_us = max(longest_us, end - start)

        return us_to_s(longest_us)

    @property
    def up_intervals(self) -> Intervals: ...

    @property
    def pct_down(self) -> float:
        match_us = self.match_span[1] - self.match_span[0]
        return self.total_down_s / us_to_s(match_us)

    def is_down(self, ts_us: int) -> bool:
        if ts_us < self.match_span[0] or ts_us > self.match_span[1]:
            raise ValueError("requested ts_us not in match span")

        idx = bisect_right(self.down_intervals, ts_us, key=lambda x: x[1])

        if idx == len(self.down_intervals):
            return False

        return ts_us >= self.down_intervals[idx][0]

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
        down = down_intervals(camera_zip, match_span)

        return CameraAvailability(down, match_span)


CAMERA_HEALTH = CameraHealth
