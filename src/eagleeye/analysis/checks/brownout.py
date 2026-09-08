from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field

from eagleeye.analysis.features import ROBOT_PHASES
from eagleeye.analysis.util import (
    Check,
    CheckResult,
    Context,
    NotApplicableError,
    Severity,
    bool_intervals,
    us_to_s,
)
from eagleeye.plot import HLine, PlotSpec, Trace
from eagleeye.signals import BoolSignal, FloatSignal, TimeSeries


# ---------------------------------------------------------------------------
# analysis config and json decoding
# ---------------------------------------------------------------------------
class BrownoutConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["brownout"] = "brownout"

    voltage_signal: str = "/Robot/SystemStats/BatteryVoltage"
    brownout_signal: str = "/Robot/SystemStats/BrownedOut"

    warn_voltage: float = Field(default=7.5, ge=5.5, le=7.5)
    brownout_voltage: float = Field(default=6.8, ge=5.0, le=6.8)
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


@dataclass(frozen=True, slots=True)
class BucketSample:
    voltage: float
    bucket_level: float


def leaky_bucket(
    samples: Iterable[tuple[int, float]],
    threshold: float,
) -> TimeSeries[BucketSample]:

    bucket = 0.0
    last_time = None

    dt_cap = 40000  # 40ms max interval - don't overcount large loop overruns
    max_bucket = 50000
    leak_rate = 1

    times: list[int] = []
    buckets: list[BucketSample] = []

    for time, voltage in samples:
        if last_time is None:
            last_time = time
            continue

        deficit = threshold - voltage

        dt = min(time - last_time, dt_cap)
        dt = max(0, dt)  # protect against bad input file

        last_time = time

        if deficit > 0:
            bucket += dt * deficit

        else:
            bucket += dt * deficit * leak_rate

        bucket = max(bucket, 0)
        bucket = min(bucket, max_bucket)

        times.append(time)
        buckets.append(BucketSample(voltage=voltage, bucket_level=bucket))

    return TimeSeries[BucketSample](name="brownout_bucket", timestamps=times, values=buckets)


def low_voltage_intervals(
    buckets: Iterable[tuple[int, BucketSample]],
    voltage_threshold: float,
    bucket_threshold: float,
    buffer: int,
) -> list[tuple[int, int]]:

    intervals: list[tuple[int, int]] = []
    run_start: int | None = None
    last_low: int | None = None
    last_voltage: float | None = 13.0
    bucket_tripped: bool = False

    for time, bucket_sample in buckets:
        voltage = bucket_sample.voltage
        bucket = bucket_sample.bucket_level

        # detect potential interval, drop it if voltage > threshold and bucket didn't trip
        if voltage < voltage_threshold:
            if run_start is None:
                run_start = time
            last_low = time
        elif bucket_tripped is False:
            run_start = None
        # extend last_low one timestamp for plotting
        elif last_voltage < voltage_threshold:
            last_low = time

        last_voltage = voltage

        if bucket > bucket_threshold:
            bucket_tripped = True
        elif run_start is None or last_low is None:
            continue
        elif (time - last_low) > buffer:
            intervals.append((run_start, last_low))
            run_start = None
            last_low = None

    if run_start is not None and last_low is not None:
        intervals.append((run_start, last_low))

    return intervals


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
        brownout_voltage: float,
        trailing_buffer: float,
    ) -> None:

        self.id = "brownout"
        self.name = "Battery Brownout"
        self.voltage_signal = voltage_signal
        self.brownout_signal = brownout_signal
        self.warn_voltage = warn_voltage
        self.brownout_voltage = brownout_voltage
        self.interval_buffer = int(trailing_buffer * 1e6)

        self.levels: list[float]

    @classmethod
    def from_config(cls, cfg: BrownoutConfig) -> Self:
        return cls(
            cfg.voltage_signal,
            cfg.brownout_signal,
            warn_voltage=cfg.warn_voltage,
            brownout_voltage=cfg.brownout_voltage,
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
                # Trace("Bucket", self.bucket_levels, axis="right"),
            ],
            hlines=[
                HLine(self.warn_voltage, f"warn {self.warn_voltage}V"),
                HLine(self.brownout_voltage, f"brownout {self.brownout_voltage}V"),
            ],
            bool_spans=[
                [(int(a), int(b)) for a, b in result.warn_intervals],
                [(int(a), int(b)) for a, b in result.fail_intervals],
            ],
            y_label="Volts",
        )

    def run(self, ctx: Context) -> CheckResult:

        v_signal = ctx.require(self.voltage_signal, FloatSignal)
        b_signal = ctx.require(self.brownout_signal, BoolSignal)

        match_span = ctx.feature(ROBOT_PHASES).match_span

        if match_span is None:
            raise NotApplicableError("no enabled period in log")

        # compute bucket levels
        v_zip = v_signal.zip_between_ts(*match_span)
        buckets = leaky_bucket(v_zip, self.warn_voltage)

        # find intervals with bucket level > threshold
        # threshold = 10,000
        bucket_zip = buckets.zip_between_ts(*match_span)
        intervals = low_voltage_intervals(
            bucket_zip, self.warn_voltage, 10000, self.interval_buffer
        )

        # bucket levels for plotting in dev mode
        self.bucket_levels = buckets.project(lambda s: s.bucket_level, name="bucket_level")

        b_zip: list[float] = [
            us_to_s(t, match_span)
            for t, v in zip(b_signal.timestamps, b_signal.values, strict=True)
            if v is True
        ]

        min_v = min((val for val in v_signal.values), default=float("nan"))
        details = {
            "min_voltage": round(min_v, 3),
            "warn_voltage": self.warn_voltage,
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

        fail_intervals = bool_intervals(b_signal)

        return CheckResult(
            self.id,
            self.name,
            sev,
            summary,
            details,
            warn_intervals=intervals,
            fail_intervals=fail_intervals,
        )
