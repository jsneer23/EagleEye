from collections.abc import Iterable

from eagleeye.analysis.features import CAMERA_HEALTH, ROBOT_PHASES
from eagleeye.analysis.util import (
    Check,
    CheckResult,
    Context,
    Severity,
)
from eagleeye.config.models import AprilTagThresholds, CameraSignals
from eagleeye.errors import NotApplicableError
from eagleeye.signals import FloatSignal


# ---------------------------------------------------------------------------
# helper functions
# ---------------------------------------------------------------------------
def calc_accepted_us(
    accepted: Iterable[tuple[int, float]], timeout_us: int, match_end_us: int
) -> int:

    valid_until = -1
    total_accepted_us = 0

    for ts_us, _ in accepted:
        next_valid = min(ts_us + timeout_us, match_end_us)
        if ts_us > valid_until:
            if ts_us + timeout_us <= match_end_us:
                total_accepted_us += timeout_us
            else:
                total_accepted_us += match_end_us - ts_us
        else:
            total_accepted_us += next_valid - valid_until
        valid_until = next_valid

    return total_accepted_us


class AprilTagCheck(Check[CameraSignals, AprilTagThresholds]):
    id = "april_tag"
    name = "April Tag Seen"
    source = "cameras"

    @property
    def result_id(self) -> str:
        return f"{self.id}::{self.instance}"

    def run(self, ctx: Context) -> CheckResult:

        sev = Severity.OK

        signal = ctx.require(self.signals.accepted_ts_us, FloatSignal)

        match_span = ctx.feature(ROBOT_PHASES).match_span
        camera_health = ctx.feature(CAMERA_HEALTH, self.instance)

        if match_span is None:
            raise NotApplicableError("no enabled period in log")

        accepted_zip = signal.zip_between_ts(*match_span)
        timeout_us = self.thresholds.accepted_tag_timeout_ms * 1000

        total_accepted_us = calc_accepted_us(accepted_zip, timeout_us, match_span[1])

        pct = total_accepted_us / camera_health.total_up_us

        summary = f"camera sees tag {pct * 100:.1f}% of available uptime"

        sev = Severity.OK
        if pct <= self.thresholds.fail_pct:
            sev = Severity.FAIL
        elif pct <= self.thresholds.warn_pct:
            sev = Severity.WARNING

        return CheckResult(self.id, self.instance, sev, summary)
