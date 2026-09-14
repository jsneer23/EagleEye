from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field

from eagleeye.analysis.features import RADIO_JSON, ROBOT_PHASES
from eagleeye.analysis.util import (
    Check,
    CheckResult,
    Context,
    NotApplicableError,
    Severity,
    threshold_excursions,
)
from eagleeye.plot import HLine, PlotSpec, Trace
from eagleeye.signals import FloatSignal


# ---------------------------------------------------------------------------
# analysis config and json decoding
# ---------------------------------------------------------------------------
class RadioConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["radio"] = "radio"

    radio_dbm: str = "/Robot/RadioStatus/StatusJson/networkStatus6/signalDbm"
    radio_snr: str = "/Robot/RadioStatus/StatusJson/networkStatus6/signalNoiseRatio"

    err_dbm: int = Field(default=-70)  # likely dropouts
    warn_dbm: int = Field(default=-60)  # warn
    info_dbm: int = Field(default=-50)  # acceptable but not ideal
    err_snr: int = Field(default=20)  # severe, expect packet loss
    warn_snr: int = Field(default=30)  # marginal
    info_snr: int = Field(default=40)  # ok but could be better

    merge_intervals_gap_s: float = Field(default=0.1, ge=0.05, le=0.5)
    min_interval_duration_s: float = Field(default=0, ge=0, le=0.25)


class RadioJSON(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    defaults: dict[str, float] = Field(default_factory=dict)
    instances: dict[str, dict[str, Any]] = Field(min_length=1)

    def build(self) -> list[RadioConfig]:
        return [
            RadioConfig.model_validate(self.defaults | body | {"type": label})
            for label, body in self.instances.items()
        ]


class RadioCheck(Check):
    def __init__(
        self,
        radio_dbm: str,
        radio_snr: str,
        *,
        err_dbm: int,
        warn_dbm: int,
        info_dbm: int,
        err_snr: int,
        warn_snr: int,
        info_snr: int,
    ) -> None:

        self.id = "radio"
        self.name = "Radio Health Check"

        self.radio_dbm = radio_dbm
        self.radio_snr = radio_snr

        self.err_dbm = err_dbm
        self.warn_dbm = warn_dbm
        self.info_dbm = info_dbm
        self.err_snr = err_snr
        self.warn_snr = warn_snr
        self.info_snr = info_snr

    @classmethod
    def from_config(cls, cfg: RadioConfig) -> Self:
        return cls(
            cfg.radio_dbm,
            cfg.radio_snr,
            err_dbm=cfg.err_dbm,
            warn_dbm=cfg.warn_dbm,
            info_dbm=cfg.info_dbm,
            err_snr=cfg.err_snr,
            warn_snr=cfg.warn_snr,
            info_snr=cfg.info_snr,
        )

    def plot_spec(self, ctx: Context, result: CheckResult) -> PlotSpec | None:

        match_span = ctx.feature(ROBOT_PHASES).match_span

        if match_span is None:
            return None

        return PlotSpec(
            title=self.name,
            t0_us=match_span[0],
            traces=[
                Trace("Battery Voltage", ctx.require(self.radio_dbm, FloatSignal)),
                Trace("Battery Voltage", ctx.require(self.radio_snr, FloatSignal)),
                # Trace("Bucket", self.bucket_levels, axis="right"),
            ],
            hlines=[
                HLine(self.warn_dbm, f"warn {self.warn_dbm}"),
                HLine(self.err_dbm, f"err {self.err_dbm}"),
                HLine(self.warn_snr, f"warn {self.warn_snr}"),
                HLine(self.err_snr, f"err {self.err_snr}"),
            ],
            bool_spans=[
                [(int(a), int(b)) for a, b in result.warn_intervals],
                [(int(a), int(b)) for a, b in result.fail_intervals],
            ],
            y_label="Volts",
        )

    def run(self, ctx: Context) -> CheckResult:

        match_span = ctx.feature(ROBOT_PHASES).match_span

        if match_span is None:
            raise NotApplicableError("no enabled period in log")

        radio_telemetry = ctx.feature(RADIO_JSON).series

        # compute bucket levels
        dbm_signal = radio_telemetry.project(lambda s: s.radio_dbm, name="radio_dbm")
        dbm_zip = dbm_signal.zip_between_ts(*match_span)
        dbm_seconds_over, dbm_intervals = threshold_excursions(
            dbm_zip, threshold=self.err_dbm, max_gap_s=7
        )

        snr_signal = radio_telemetry.project(lambda s: s.radio_snr, name="radio_snr")
        snr_zip = snr_signal.zip_between_ts(*match_span)
        snr_seconds_over, snr_intervals = threshold_excursions(
            snr_zip, threshold=self.err_snr, max_gap_s=7
        )

        details = {"low_dbm": len(dbm_intervals), "low_snr": len(snr_intervals)}

        if snr_intervals or dbm_intervals:
            sev = Severity.WARNING
            summary = ""
            if snr_intervals:
                summary = summary + (
                    f"signal to noise ratio was above threshold {self.warn_snr} for"
                    f"{snr_seconds_over}s between intervals {snr_intervals}\n"
                )
            if dbm_intervals:
                summary = summary + (
                    f"radio dbm was below threshold {self.warn_dbm} for {dbm_seconds_over}s between"
                    f"intervals {dbm_intervals}\n"
                )
        else:
            sev = Severity.OK
            summary = "OK"

        return CheckResult(
            self.id,
            self.name,
            sev,
            summary,
            details,
        )
