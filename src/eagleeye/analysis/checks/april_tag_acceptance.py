from eagleeye.analysis.features import ROBOT_PHASES
from eagleeye.analysis.util import (
    Check,
    CheckResult,
    Context,
    Severity,
)
from eagleeye.config.models import AprilTagThresholds, CameraSignals
from eagleeye.errors import NotApplicableError
from eagleeye.signals import BoolSignal

# ---------------------------------------------------------------------------
# helper functions
# ---------------------------------------------------------------------------


class AprilTagCheck(Check[CameraSignals, AprilTagThresholds]):
    id = "april_tag"
    name = "April Tag Seen"
    source = "cameras"

    @property
    def result_id(self) -> str:
        return f"{self.id}::{self.instance}"

    def run(self, ctx: Context) -> CheckResult:

        sev = Severity.OK
        summary_arr: list[str] = []

        signal = ctx.require(self.signals.accepted_ts_us, BoolSignal)

        match_span = ctx.feature(ROBOT_PHASES).match_span
        enabled_us = ctx.feature(ROBOT_PHASES).enabled_time_us  # type: ignore  # noqa: F841

        if match_span is None:
            raise NotApplicableError("no enabled period in log")

        camera_zip = signal.zip_between_ts(*match_span)  # type: ignore  # noqa: F841

        if sev == Severity.OK:
            summary = "experienced no downtime."
        else:
            summary = "\n".join(summary_arr)

        return CheckResult(self.id, self.instance, sev, summary)
