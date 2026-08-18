from collections.abc import Iterator
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field

from eagleeye.analysis.features import ROBOT_PHASES
from eagleeye.analysis.util import NotApplicableError
from eagleeye.signals import BoolSignal

from ..util import Check, CheckResult, Context, Severity


# ---------------------------------------------------------------------------
# analysis config and json decoding
# ---------------------------------------------------------------------------
class CameraHealthConfig(BaseModel):
    camera_label: str
    health_signal: str

    warn_sustained_s: float = Field(default=0.5, ge=0.1, le=5)

class CameraHealthJSON(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    defaults: dict[str, float] = Field(default_factory=dict)
    instances: dict[str, dict[str, Any]] = Field(min_length=1)

    def build(self) -> list[CameraHealthConfig]:
        return [
            CameraHealthConfig.model_validate(self.defaults | body | {"camera_label": label})
            for label, body in self.instances.items()
        ]

# ---------------------------------------------------------------------------
# helper functions
# ---------------------------------------------------------------------------
def camera_down(samples: Iterator[tuple[int, bool]]) -> tuple[bool, int, int]:
    return (False, 0, 0)

class CameraHealthCheck(Check):

    def __init__(
        self,
        camera_label: str,
        health_signal: str,
        *,
        sustained: float,
    ) -> None:
        self.id = f"camera_health::{camera_label}"
        self.camera_label = camera_label
        self.health_signal = health_signal
        self.sustained = sustained

    @classmethod
    def from_config(cls, cfg: CameraHealthConfig) -> Self:
        return cls(
            cfg.camera_label,
            cfg.health_signal,
            sustained = cfg.warn_sustained_s,
        )

    def run(self, ctx: Context) -> CheckResult:

        sev = Severity.OK
        summary_arr: list[str] = []

        signal = ctx.require(self.health_signal, BoolSignal)

        match_span = ctx.feature(ROBOT_PHASES).match_span

        if match_span is None:
            raise NotApplicableError("no enabled period in log")

        camera_zip = signal.zip_between_ts(*match_span)

        down, pct, longest = camera_down(camera_zip)

        if down:
            if longest > self.sustained or pct > 0.05:
                sev = Severity.FAIL
                summary_arr.append(f"{self.camera_label}: experienced maximum sustained downtime"
                                   f" for {longest*1000:.1f}s and was down for {pct*100:.0f}% of"
                                    " the match")
            elif sev == Severity.OK:
                sev = Severity.WARNING
                summary_arr.append(f"{self.camera_label}: experienced brief downtime"
                                    f" (<{self.sustained*1000:.0f}ms) and was down for"
                                    f" {pct*100:.0f}% of the match"
                                    )

        if sev == Severity.OK:
            summary = "experienced no downtime."
        else:
            summary = "\n".join(summary_arr)

        return CheckResult(self.id, self.camera_label, sev, summary)
