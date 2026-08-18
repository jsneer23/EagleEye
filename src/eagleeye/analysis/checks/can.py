from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field

from eagleeye.analysis.util import (
    Check,
    CheckResult,
    Context,
    Severity,
    clean_intervals,
    threshold_excursions,
)
from eagleeye.signals import FloatSignal


# ---------------------------------------------------------------------------
# analysis config and json decoding
# ---------------------------------------------------------------------------
class CanConfig(BaseModel):
    bus_label: str
    bus_signal: str

    warn_sustained_level: float = Field(default=0.8, ge=0.6, le=0.9)
    warn_sustained_s: float = Field(default=0.5, ge=0.2, le=3)
    warn_peak: float = Field(default=0.95, ge=0.75, le=0.99)

class CanUtilJSON(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    defaults: dict[str, float] = Field(default_factory=dict)
    instances: dict[str, dict[str, Any]] = Field(min_length=1)

    def build(self) -> list[CanConfig]:
        return [
            CanConfig.model_validate(self.defaults | body | {"bus_label": label})
            for label, body in self.instances.items()
        ]

# ---------------------------------------------------------------------------
# helper functions
# ---------------------------------------------------------------------------

class CanUtilizationCheck(Check):

    def __init__(
        self,
        bus_label: str,
        bus_signal: str,
        *,
        warn_level: float,
        sustained: float,
        warn_peak: float,
    ) -> None:

        self.id = f"can_util::{bus_label}"
        self.name = f"CAN Utilization - {bus_label}"
        self.signal_name = bus_signal
        self.bus_label = bus_label
        self.warn = warn_level
        self.warn_peak = warn_peak
        self.sustained = sustained

    @classmethod
    def from_config(cls, cfg: CanConfig) -> Self:
        return cls(
            cfg.bus_label,
            cfg.bus_signal,
            warn_level = cfg.warn_sustained_level,
            sustained = cfg.warn_sustained_s,
            warn_peak=cfg.warn_peak
        )


    def run(self, ctx: Context) -> CheckResult:

        signal = ctx.require(self.signal_name, FloatSignal)

        if len(signal.values) < 2:
            return CheckResult(self.id,
                self.name,
                Severity.NOT_APPLICABLE,
                f"Too few samples for {self.bus_label}."
            )

        peak = max(signal.values)
        mean = sum(signal.values) / len(signal.values)
        seconds_over, raw = threshold_excursions(signal.timestamps, signal.values, self.warn)
        intervals = clean_intervals(raw, min_duration_s=0.1)
        longest = max((b-a for a,b in intervals), default=0.0)

        details = {
            "peak": round(peak, 4), "mean": round(mean, 4),
            "warn_threshold": self.warn,
            "seconds_over_warn": round(seconds_over, 3),
            "longest_excursion_s": round(longest, 3),
            "samples": len(signal.values),
        }

        if longest >= self.sustained:
            sev = Severity.FAIL
            summary = (f"{self.bus_label}: sustained over {self.warn*100:.0f}% for "
                       f"{longest:.1f}s (peak {peak*100:.0f}%) — frames likely dropping.")
        elif peak >= self.warn_peak:
            sev = Severity.WARNING
            summary = (f"{self.bus_label}: brief spikes to {peak*100:.0f}% but never "
                       f"sustained (longest {longest*1000:.0f}ms).")
        else:
            sev = Severity.OK
            summary = f"{self.bus_label}: healthy, peak {peak*100:.0f}%."

        return CheckResult(self.id, self.name, sev, summary, details, intervals)
