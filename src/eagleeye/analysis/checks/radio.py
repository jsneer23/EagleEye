from eagleeye.analysis.features import RADIO_JSON, ROBOT_PHASES
from eagleeye.analysis.util import (
    Check,
    CheckResult,
    Context,
    Severity,
    threshold_excursions_below,
    us_to_s,
)
from eagleeye.config.models import CommsSignals, RadioThresholds
from eagleeye.errors import NotApplicableError
from eagleeye.plot import HLine, PlotSpec, Trace


class RadioCheck(Check[CommsSignals, RadioThresholds]):
    id = "radio_signal"
    name = "Radio Signal"
    source = "comms"

    def plot_spec(self, ctx: Context, result: CheckResult) -> PlotSpec | None:

        match_span = ctx.feature(ROBOT_PHASES).match_span
        radio_telemetry = ctx.feature(RADIO_JSON).series

        if match_span is None:
            return None

        return PlotSpec(
            title=self.name,
            t0_us=match_span[0],
            traces=[
                Trace(
                    "DBM",
                    radio_telemetry.project(lambda s: s.radio_dbm, name="radio_dbm"),
                ),
                Trace(
                    "SNR",
                    radio_telemetry.project(lambda s: s.radio_snr, name="radio_snr"),
                ),
            ],
            hlines=[
                HLine(self.thresholds.warn_dbm, f"warn {self.thresholds.warn_dbm}"),
                HLine(self.thresholds.err_dbm, f"err {self.thresholds.err_dbm}"),
                HLine(self.thresholds.warn_snr, f"warn {self.thresholds.warn_snr}"),
                HLine(self.thresholds.err_snr, f"err {self.thresholds.err_snr}"),
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
        dbm_below_us, dbm_intervals = threshold_excursions_below(
            dbm_zip, threshold=self.thresholds.err_dbm, max_gap_us=int(7e6)
        )
        dbm_below_s = us_to_s(dbm_below_us)

        snr_signal = radio_telemetry.project(lambda s: s.radio_snr, name="radio_snr")
        snr_zip = snr_signal.zip_between_ts(*match_span)
        snr_below_us, snr_intervals = threshold_excursions_below(
            snr_zip, threshold=self.thresholds.err_snr, max_gap_us=int(7e6)
        )
        snr_below_s = us_to_s(snr_below_us)

        details = {"low_dbm": len(dbm_intervals), "low_snr": len(snr_intervals)}

        if snr_intervals or dbm_intervals:
            sev = Severity.WARNING
            summary = ""
            if snr_intervals:
                summary = summary + (
                    f"signal to noise ratio was above threshold {self.thresholds.warn_snr} for"
                    f"{snr_below_s}s between intervals {snr_intervals}\n"
                )
            if dbm_intervals:
                summary = summary + (
                    f"radio dbm was below threshold {self.thresholds.warn_dbm} for "
                    f" {dbm_below_s}s between intervals {dbm_intervals}\n"
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
