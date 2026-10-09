from eagleeye.analysis.features import ROBOT_PHASES
from eagleeye.analysis.util import (
    Check,
    CheckResult,
    Context,
    Severity,
    clean_intervals,
    threshold_excursions_above,
    us_to_s,
)
from eagleeye.analysis.util.context import NotApplicableError
from eagleeye.config.models import CanSignals, CanUtilThresholds
from eagleeye.plot import HLine, PlotSpec, Trace
from eagleeye.signals import FloatSignal

# ---------------------------------------------------------------------------
# helper functions
# ---------------------------------------------------------------------------


class CanUtilCheck(Check[CanSignals, CanUtilThresholds]):
    id = "can_util"
    name = "Can Utilization"
    source = "can"

    @property
    def result_id(self) -> str:
        return f"{self.id}::{self.instance}"

    def plot_spec(self, ctx: Context, result: CheckResult) -> PlotSpec | None:

        match_span = ctx.feature(ROBOT_PHASES).match_span

        if match_span is None:
            return None

        return PlotSpec(
            title=self.name,
            t0_us=match_span[0],
            traces=[
                Trace("Util %", ctx.require(self.signals.util, FloatSignal)),
            ],
            hlines=[
                HLine(
                    self.thresholds.warn_sustained_level,
                    f"warn {self.thresholds.warn_sustained_level * 100:.1f}%",
                ),
            ],
            bool_spans=[
                [(int(a), int(b)) for a, b in result.warn_intervals],
            ],
            y_label="Util %",
        )

    def run(self, ctx: Context) -> CheckResult:

        match_span = ctx.feature(ROBOT_PHASES).match_span

        if match_span is None:
            raise NotApplicableError("no enabled period in log")

        signal = ctx.require(self.signals.util, FloatSignal)

        if len(signal.values) < 2:
            return CheckResult(
                self.id,
                self.name,
                Severity.NOT_APPLICABLE,
                f"Too few samples for {self.result_id}.",
            )

        peak = max(signal.values)
        mean = sum(signal.values) / len(signal.values)

        can_zip = signal.zip_between_ts(*match_span)

        us_over, raw = threshold_excursions_above(can_zip, self.thresholds.warn_sustained_level)
        intervals = clean_intervals(raw)
        longest_us = max((b - a for a, b in intervals), default=0)

        seconds_over = us_to_s(us_over)
        longest_s = us_to_s(longest_us)

        details = {
            "peak": round(peak, 4),
            "mean": round(mean, 4),
            "warn_threshold": self.thresholds.warn_sustained_level,
            "seconds_over_warn": round(seconds_over, 3),
            "longest_excursion_s": round(longest_s, 3),
            "samples": len(signal.values),
        }

        if longest_s >= self.thresholds.warn_sustained_s:
            sev = Severity.FAIL
            summary = (
                f"{self.result_id}: sustained over {self.thresholds.warn_sustained_level * 100:.0f}"
                f"% for {longest_s:.1f}s (peak {peak * 100:.0f}%) — frames likely dropping."
            )
        elif peak >= self.thresholds.warn_peak:
            sev = Severity.WARNING
            summary = (
                f"{self.result_id}: brief spikes to {peak * 100:.0f}% but never "
                f"sustained (longest {longest_s * 1000:.0f}ms)."
            )
        else:
            sev = Severity.OK
            summary = f"{self.result_id}: healthy, peak {peak * 100:.0f}%."

        return CheckResult(self.id, self.name, sev, summary, details, warn_intervals=intervals)
