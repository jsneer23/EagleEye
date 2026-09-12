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
    leaky_bucket,
    low_intervals,
    match_time_s,
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
    brownout_voltage: float = Field(default=6.8, ge=5.0, le=6.8)
    merge_intervals_gap_s: float = Field(default=0.1, ge=0.05, le=0.5)
    min_interval_duration_s: float = Field(default=0, ge=0, le=0.25)


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
        merge_intervals_gap_s: float,
        min_interval_duration_s: float,
    ) -> None:

        self.id = "brownout"
        self.name = "Battery Brownout"
        self.voltage_signal = voltage_signal
        self.brownout_signal = brownout_signal
        self.warn_voltage = warn_voltage
        self.brownout_voltage = brownout_voltage
        self.merge_intervals_gap_s = merge_intervals_gap_s
        self.min_interval_duration_s = min_interval_duration_s

        self.levels: list[float]

    @classmethod
    def from_config(cls, cfg: BrownoutConfig) -> Self:
        return cls(
            cfg.voltage_signal,
            cfg.brownout_signal,
            warn_voltage=cfg.warn_voltage,
            brownout_voltage=cfg.brownout_voltage,
            merge_intervals_gap_s=cfg.merge_intervals_gap_s,
            min_interval_duration_s=cfg.min_interval_duration_s,
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
        intervals = low_intervals(
            bucket_zip,
            signal_threshold=self.warn_voltage,
            bucket_threshold=10000,
            merge_intervals_gap_s=self.merge_intervals_gap_s,
            min_duration_s=self.min_interval_duration_s,
        )

        # bucket levels for plotting in dev mode
        self.bucket_levels = buckets.project(lambda s: s.bucket_level, name="bucket_level")

        b_zip: list[float] = [
            match_time_s(t, match_span)
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
                f"systemcore browned out {len(b_zip)}x between [{window}]; "
                f"voltage dropped to {min_v:.2f}V."
            )
        elif intervals:
            sev = Severity.WARNING
            summary = (
                f"voltage dipped below {self.warn_voltage}V "
                f"{len(intervals)}x (min {min_v:.2f}V) without browning out."
            )
        else:
            sev = Severity.OK
            summary = f"battery healthy, min voltage {min_v:.2f}V."

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
