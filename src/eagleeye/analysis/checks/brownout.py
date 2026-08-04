
from collections.abc import Iterator

from eagleeye.analysis.features import ROBOT_PHASES
from eagleeye.analysis.util import (
    Check,
    CheckResult,
    Context,
    NotApplicableError,
    Severity,
    us_to_s,
)
from eagleeye.signals import BoolSignal, FloatSignal


# ---------------------------------------------------------------------------
# helper functions
# ---------------------------------------------------------------------------
def low_voltage_intervals(samples: Iterator[tuple[int, float]],
                          threshold: float,
                          buffer: float) -> tuple[list[tuple[float, float]], int]:

    intervals: list[tuple[float, float]] = []
    run_start: float | None = None
    last_low: float | None = None
    num_low: int = 0

    for time, voltage in samples:
        if voltage < threshold:
            num_low += 1
            last_low = time
            if run_start is None:
                run_start = time
        elif run_start is not None and last_low is not None:
            if (time - last_low) > buffer:
                intervals.append((run_start, last_low + buffer))
                run_start = None
                last_low = None

    if run_start is not None and last_low is not None:
        intervals.append((run_start, last_low + buffer))

    return intervals, num_low

class BrownoutCheck(Check):

    def __init__(
        self,
        voltage_signal: str = "/Robot/SystemStats/BatteryVoltage",
        brownout_signal: str = "/Robot/SystemStats/BrownedOut",
        *,
        warn_voltage: float = 7.5,
        trailing_buffer: float = 0.1,
    ) -> None:

        self.id = f"brownout - warn at {warn_voltage}V"
        self.name = "Battery Brownout"
        self.voltage_signal = voltage_signal
        self.brownout_signal = brownout_signal
        self.warn_voltage = warn_voltage
        self.interval_buffer = trailing_buffer

    def run(self, ctx: Context) -> CheckResult:

        v_signal = ctx.require(self.voltage_signal, FloatSignal)
        b_signal = ctx.require(self.brownout_signal, BoolSignal)

        match_span = ctx.feature(ROBOT_PHASES).match_span

        if match_span is None:
            raise NotApplicableError("no enabled period in log")

        v_zip = v_signal.zip_between_ts(*match_span)

        intervals, num_low = low_voltage_intervals(v_zip,
                                                   self.warn_voltage,
                                                   self.interval_buffer)

        b_zip: list[float] = [
            us_to_s(t, match_span) for t,v in zip(b_signal.timestamps, b_signal.values, strict=True)
            if v is True
        ]

        min_v = min((val for val in v_signal.values), default=float("nan"))
        details = {
            "min_voltage": round(min_v, 3),
            "warn_voltage": self.warn_voltage,
            "low_samples": num_low,
            "low_intervals": len(intervals),
            "brownout_events": len(b_signal.timestamps),
        }

        if len(b_signal.timestamps) > 0:
            sev = Severity.FAIL
            window = (f"{b_zip[0]:.1f},{b_zip[-1]:.1f}s"
                      if len(b_zip) > 1 else f"{b_zip[0]:.1f}s")
            summary = (f"rio browned out {len(b_zip)}x between [{window}]; "
                       f"voltage dropped to {min_v:.2f}V.")
        elif intervals:
            sev = Severity.WARNING
            summary = (f"Voltage dipped below {self.warn_voltage}V "
                       f"{len(intervals)}x (min {min_v:.2f}V) without browning out.")
        else:
            sev = Severity.OK
            summary = f"Battery healthy, min voltage {min_v:.2f}V."

        return CheckResult(self.id, self.name, sev, summary, details, intervals)
