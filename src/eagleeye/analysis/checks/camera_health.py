from collections.abc import Iterator

from eagleeye.analysis.features import ROBOT_PHASES
from eagleeye.analysis.util import NotApplicableError
from eagleeye.signals import BoolSignal

from ..util import Check, CheckResult, Context, Severity


# ---------------------------------------------------------------------------
# helper functions
# ---------------------------------------------------------------------------
def camera_down(samples: Iterator[tuple[int, bool]]) -> tuple[bool, int, int]:
    return (False, 0, 0)

class CameraHealthCheck(Check):

    def __init__(
        self,
        sustained: float = 0.5,
    ) -> None:
        self.id = ""
        self.name = "Camera Health Check"
        self.health_signals = {
            "back_right_cam": "/Robot//Vision/back_right_cam/April Tag Cam Connected/",
            "cam_back_left":  "/Robot//Vision/cam_back_left/April Tag Cam Connected/",
            "cam_back_right": "/Robot//Vision/cam_back_right/April Tag Cam Connected/",
            "cam2026_02":     "/Robot//Vision/cam2026_02/April Tag Cam Connected/",
        }

        self.sustained = sustained


    def run(self, ctx: Context) -> CheckResult:

        sev = Severity.OK
        summary_arr: list[str] = []

        for cam_name, val in self.health_signals.items():
            signal = ctx.require(val, BoolSignal)

            match_span = ctx.feature(ROBOT_PHASES).match_span

            if match_span is None:
                raise NotApplicableError("no enabled period in log")

            camera_zip = signal.zip_between_ts(*match_span)

            down, pct, longest = camera_down(camera_zip)

            if down:
                if longest > self.sustained or pct > 0.05:
                    sev = Severity.FAIL
                    summary_arr.append(f"{cam_name}: experienced maximum sustained downtime for "
                       f"{longest*1000:.1f}s and was down for {pct*100:.0f}% of the match")
                elif sev == Severity.OK:
                    sev = Severity.WARNING
                    summary_arr.append(f"{cam_name}: experienced brief downtime "
                                       f"(<{self.sustained*1000:.0f}ms) and was down for "
                                       f"{pct*100:.0f}% of the match"
                                       )

        if sev == Severity.OK:
            summary = "No camera signal experienced downtime."
        else:
            summary = "\n".join(summary_arr)

        return CheckResult(self.id, self.name, sev, summary)
