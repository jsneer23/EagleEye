from bisect import bisect_right
from dataclasses import dataclass

from eagleeye.parsers.signals import BoolSignal, IntSignal

from ..util import Context, Feature, Interval, Intervals


@dataclass(frozen=True)
class RobotPhases:
    match_start : int
    auton: Intervals
    teleop: Intervals
    log_truncated: bool = False

    @property
    def match_span(self) -> Interval | None:

        if not self.auton:
            if not self.teleop:
                return None
            return (self.teleop[0][0], self.teleop[-1][1])
        if not self.teleop:
            return (self.auton[0][0], self.auton[-1][1])

        return (self.auton[0][0], self.teleop[-1][1])

    def __rich__(self) -> str:

        if not self.auton and not self.teleop:
            return "No enabled period in log"

        auton_str = teleop_str = ""
        auton_len = teleop_len = 0

        for start, end in self.auton:
            auton_len += end - start
            start = (start-self.match_start)*1e-6
            end = (end-self.match_start)*1e-6
            auton_str += f"({start:.2f},  {end:.2f})"

        for start, end in self.teleop:
            teleop_len += end - start
            start = (start-self.match_start)*1e-6
            end = (end-self.match_start)*1e-6
            teleop_str += f"({start:.2f}, {end:.2f})"

        auton_float = auton_len * 1e-6
        teleop_float = teleop_len * 1e-6

        result = (
            f"auton  enabled for  {auton_float:.2f}s on intervals [  {auton_str} ] \n"
            f"teleop enabled for {teleop_float:.2f}s on intervals [ {teleop_str} ]"
        )

        return result


def corrupted_log_disable(timestamps: list[int], values: list[int], last_log_timestamp: int) -> int:

    for t, v in zip(timestamps, values, strict=True):
        if v == 48:
            return t

    return last_log_timestamp


def true_intervals(timestamps: list[int],
                   values: list[bool],
                   corrupted_log_end: int) -> tuple[Intervals, bool]:

    intervals: Intervals = []
    start: int | None = None
    truncated: bool = False

    for t, v in zip(timestamps, values, strict=True):
        if v and start is None:
            start = t
        elif not v and start is not None:
            intervals.append((start, t))
            start = None

    if start is not None:
        intervals.append((start, corrupted_log_end))
        truncated = True

    return intervals, truncated

def held_value(times: list[int], vals: list[bool], t: int, default: bool = False) -> bool:

    i = bisect_right(times, t) - 1

    return vals[i] if i >= 0 else default

class EnabledIntervals(Feature[RobotPhases]):

    key = "enabled_intervals"
    enabled: str

    def compute(self, ctx: Context) -> RobotPhases:

        enabled = ctx.require("DS:enabled", BoolSignal)
        auto = ctx.require("DS:autonomous", BoolSignal)
        fms_control = ctx.require("NT:/FMSInfo/FMSControlData", IntSignal)
        last_log_timestamp = ctx.last_log_timestamp

        corrupted_log_end = corrupted_log_disable(fms_control.timestamps,
                                                  fms_control.values,
                                                  last_log_timestamp)

        enabled_intervals, truncated = true_intervals(enabled.timestamps,
                                                      enabled. values,
                                                      corrupted_log_end)

        auton = []
        teleop = []
        match_start = 0

        for start, end in enabled_intervals:

            if match_start == 0:
                match_start = start

            if held_value(auto.timestamps, auto.values, start):
                auton.append((start, end))
            else:
                teleop.append((start, end))

        return RobotPhases(match_start, auton, teleop, truncated)
