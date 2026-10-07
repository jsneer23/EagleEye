from eagleeye.analysis.features import CAMERA_HEALTH
from eagleeye.analysis.util import (
    Check,
    CheckResult,
    Context,
    Severity,
    us_to_s,
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
        summary_arr: list[str] = []

        camera = ctx.feature(CAMERA_HEALTH)

        if camera.down:
            if camera.longest_down_us > self.thresholds.warn_sustained_s or camera.pct_down > 0.05:
                sev = Severity.FAIL
                longest_down_s = us_to_s(camera.longest_down_us)
                summary_arr.append(
                    f"{self.instance}: experienced maximum sustained downtime"
                    f" for {longest_down_s:.1f}s and was down for {camera.pct_down * 100:.0f}% of"
                    " the match"
                )
            else:
                sev = Severity.WARNING
                summary_arr.append(
                    f"{self.instance}: experienced brief downtime"
                    f" (<{self.thresholds.warn_sustained_s * 1000:.0f}ms) and was down for"
                    f" {camera.pct_down * 100:.0f}% of the match"
                )

        if sev == Severity.OK:
            summary = "experienced no downtime."
        else:
            summary = "\n".join(summary_arr)

        return CheckResult(self.id, self.instance, sev, summary)
