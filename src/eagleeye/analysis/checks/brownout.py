from collections.abc import Iterator
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field

from eagleeye.analysis.features import ROBOT_PHASES
from eagleeye.analysis.util import (
    Check,
    CheckResult,
    Context,
    NotApplicableError,
    Severity,
    us_to_s,
)
from eagleeye.plot import HLine, PlotSpec, Trace
from eagleeye.signals import BoolSignal, FloatSignal


# ---------------------------------------------------------------------------
# analysis config and json decoding
# ---------------------------------------------------------------------------
class BrownoutConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["brownout"] = "brownout"

    voltage_signal: str = "/Robot/SystemStats/BatteryVoltage"
    brownout_signal: str = "/Robot/SystemStats/BrownedOut"

    warn_voltage: float = Field(default=7.5, ge=5.5, le=7.5)
    trailing_buffer: float = Field(default=0.1, ge=0.05, le=0.5)


class BrownoutJSON(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    defaults: dict[str, float] = Field(default_factory=dict)
    instances: dict[str, dict[str, Any]] = Field(min_length=1)

    def build(self) -> list[BrownoutConfig]:
        return [
            BrownoutConfig.model_validate(self.defaults | body | {"type": label})
            for label, body in self.instances.items()
        ]


# ---------------------------------------------------------------------------
# helper functions
# ---------------------------------------------------------------------------


def leaky_bucket(
    samples: Iterator[tuple[int, float]], threshold: float
) -> tuple[list[tuple[int, int]], int]:

    bucket = 0.0
    last_time = 0
    capacity = 100000
    overflowing = False
    overflow_start = 0
    intervals: list[tuple[int, int]] = []
    leak_rate = 0.5

    num_low = 0

    for time, voltage in samples:
        dt = time - last_time
        last_time = time

        if voltage < threshold:
            num_low += 1
            bucket += dt
        else:
            bucket -= dt * leak_rate

        bucket = max(bucket, 0)

        if bucket > capacity:
            if not overflowing:
                overflowing = True
                overflow_start = time
        elif overflowing:
            overflowing = False
            intervals.append((overflow_start, time))

    return intervals, num_low


def low_voltage_intervals(
    samples: Iterator[tuple[int, float]], threshold: float, buffer: int
) -> tuple[list[tuple[int, int]], int]:

    intervals: list[tuple[int, int]] = []
    run_start: float | None = None
    last_low: int | None = None
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


# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------


# class BrownoutCheck(Check[BrownoutConfig]):
class BrownoutCheck(Check):
    def __init__(
        self,
        voltage_signal: str,
        brownout_signal: str,
        *,
        warn_voltage: float,
        trailing_buffer: float,
    ) -> None:

        self.id = "brownout"
        self.name = "Battery Brownout"
        self.voltage_signal = voltage_signal
        self.brownout_signal = brownout_signal
        self.warn_voltage = warn_voltage
        self.interval_buffer = int(trailing_buffer * 1e6)

    @classmethod
    def from_config(cls, cfg: BrownoutConfig) -> Self:
        return cls(
            cfg.voltage_signal,
            cfg.brownout_signal,
            warn_voltage=cfg.warn_voltage,
            trailing_buffer=cfg.trailing_buffer,
        )

    def plot_spec(self, ctx: Context, result: CheckResult) -> PlotSpec | None:
        match_span = ctx.feature(ROBOT_PHASES).match_span
        if match_span is None:
            return None

        return PlotSpec(
            title=self.name,
            t0_us=match_span[0],
            traces=[
                Trace("Battery Voltage", ctx.require(self.voltage_signal, FloatSignal)),
                Trace("Browned Out", ctx.require(self.brownout_signal, BoolSignal), axis="right"),
            ],
            hlines=[HLine(self.warn_voltage, f"warn {self.warn_voltage}V")],
            bool_spans=[(int(a), int(b)) for a, b in result.intervals],
            y_label="Volts",
        )

    def run(self, ctx: Context) -> CheckResult:

        v_signal = ctx.require(self.voltage_signal, FloatSignal)
        b_signal = ctx.require(self.brownout_signal, BoolSignal)

        match_span = ctx.feature(ROBOT_PHASES).match_span

        if match_span is None:
            raise NotApplicableError("no enabled period in log")

        v_zip = v_signal.zip_between_ts(*match_span)

        intervals, num_low = low_voltage_intervals(v_zip, self.warn_voltage, self.interval_buffer)

        intervals, num_low = leaky_bucket(v_zip, self.warn_voltage)

        b_zip: list[float] = [
            us_to_s(t, match_span)
            for t, v in zip(b_signal.timestamps, b_signal.values, strict=True)
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
            window = f"{b_zip[0]:.1f},{b_zip[-1]:.1f}s" if len(b_zip) > 1 else f"{b_zip[0]:.1f}s"
            summary = (
                f"rio browned out {len(b_zip)}x between [{window}]; "
                f"voltage dropped to {min_v:.2f}V."
            )
        elif intervals:
            sev = Severity.WARNING
            summary = (
                f"Voltage dipped below {self.warn_voltage}V "
                f"{len(intervals)}x (min {min_v:.2f}V) without browning out."
            )
        else:
            sev = Severity.OK
            summary = f"Battery healthy, min voltage {min_v:.2f}V."

        return CheckResult(self.id, self.name, sev, summary, details, intervals)
