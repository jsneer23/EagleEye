from eagleeye.analysis.features import ROBOT_PHASES
from eagleeye.analysis.util import (
    Check,
    CheckResult,
    Context,
    Severity,
    bool_intervals,
    leaky_bucket,
    low_intervals,
    match_time_s,
)
from eagleeye.config.models import BrownoutThresholds, PowerSignals
from eagleeye.errors import NotApplicableError
from eagleeye.plot import HLine, PlotSpec, Trace
from eagleeye.signals import BoolSignal, FloatSignal

# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------


class BrownoutCheck(Check[PowerSignals, BrownoutThresholds]):
    id = "brownout"
    name = "Battery Brownout"
    source = "power"

    def plot_spec(self, ctx: Context, result: CheckResult) -> PlotSpec | None:

        match_span = ctx.feature(ROBOT_PHASES).match_span

        if match_span is None:
            return None

        return PlotSpec(
            title=self.name,
            t0_us=match_span[0],
            traces=[
                Trace("Battery Voltage", ctx.require(self.signals.voltage_signal, FloatSignal)),
                # Trace("Bucket", self.bucket_levels, axis="right"),
            ],
            hlines=[
                HLine(self.thresholds.warn_voltage, f"warn {self.thresholds.warn_voltage}V"),
                HLine(
                    self.thresholds.brownout_voltage,
                    f"brownout {self.thresholds.brownout_voltage}V",
                ),
            ],
            bool_spans=[
                [(int(a), int(b)) for a, b in result.warn_intervals],
                [(int(a), int(b)) for a, b in result.fail_intervals],
            ],
            y_label="Volts",
        )

    def run(self, ctx: Context) -> CheckResult:

        v_signal = ctx.require(self.signals.voltage_signal, FloatSignal)
        b_signal = ctx.require(self.signals.brownout_signal, BoolSignal)

        match_span = ctx.feature(ROBOT_PHASES).match_span

        if match_span is None:
            raise NotApplicableError("no enabled period in log")

        # compute bucket levels
        v_zip = v_signal.zip_between_ts(*match_span)
        buckets = leaky_bucket(v_zip, self.thresholds.warn_voltage)

        # find intervals with bucket level > threshold
        # threshold = 10,000
        bucket_zip = buckets.zip_between_ts(*match_span)
        intervals = low_intervals(
            bucket_zip,
            signal_threshold=self.thresholds.warn_voltage,
            bucket_threshold=10000,
            merge_intervals_gap_s=self.thresholds.merge_intervals_gap_s,
            min_duration_s=self.thresholds.min_interval_duration_s,
        )

        # bucket levels for plotting in dev mode
        self.bucket_levels = buckets.project(lambda s: s.bucket_level, name="bucket_level")

        b_zip: list[float] = [
            match_time_s(t, match_span)
            for t, v in zip(b_signal.timestamps_us, b_signal.values, strict=True)
            if v is True
        ]

        min_v = min((val for val in v_signal.values), default=float("nan"))
        details = {
            "min_voltage": round(min_v, 3),
            "warn_voltage": self.thresholds.warn_voltage,
            "low_intervals": len(intervals),
            "brownout_events": len(b_signal.timestamps_us),
        }

        if len(b_zip) > 0:
            sev = Severity.FAIL
            window = f"{b_zip[0]:.1f},{b_zip[-1]:.1f}s" if len(b_zip) > 1 else f"{b_zip[0]:.1f}s"
            summary = (
                f"systemcore browned out {len(b_zip)}x between [{window}]; "
                f"voltage dropped to {min_v:.2f}V."
            )
        elif intervals:
            sev = Severity.WARNING
            summary = (
                f"voltage dipped below {self.thresholds.warn_voltage}V "
                f"{len(intervals)}x (min {min_v:.2f}V) without browning out."
            )
        else:
            sev = Severity.OK
            summary = f"min voltage {min_v:.2f}V."

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
