from eagleeye.analysis.features import CAMERA_HEALTH
from eagleeye.analysis.util import (
    Check,
    CheckResult,
    Context,
    Severity,
)
from eagleeye.config.models import CameraHealthThresholds, CameraSignals


class CameraHealthCheck(Check[CameraSignals, CameraHealthThresholds]):
    id = "camera_health"
    name = "Camera Health Check"
    source = "cameras"

    @property
    def result_id(self) -> str:
        return f"{self.id}::{self.instance}"

    def run(self, ctx: Context) -> CheckResult:

        sev = Severity.OK
        summary = ""

        camera = ctx.feature(CAMERA_HEALTH, self.instance)

        if camera.down:
            summary = (
                f"{self.instance}: experienced maximum sustained downtime for"
                f" {camera.longest_down_s:.1f}s and was down for"
                f" {camera.pct_down * 100:.0f}% of the match"
            )
            if (
                camera.longest_down_s > self.thresholds.fail_sustained_s
                or camera.pct_down > self.thresholds.fail_pct_down
            ):
                sev = Severity.FAIL
            elif (
                camera.longest_down_s > self.thresholds.warn_sustained_s
                or camera.pct_down > self.thresholds.warn_pct_down
            ):
                sev = Severity.WARNING
        else:
            summary = "experienced no downtime"

        return CheckResult(self.id, self.instance, sev, summary)
