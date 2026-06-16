from src.analysis.util import Check, CheckResult, Severity
from src.parsers.wpilog_parser import Signal

# ---------------------------------------------------------------------------
# helper functions
# ---------------------------------------------------------------------------


def low_voltage_intervals(samples: list[tuple[float, float]],
                          threshold: float,
                          buffer: float) -> tuple[list[tuple[float, float]], int]:

    intervals: list[tuple[float, float]] = []
    run_start: float | None = None
    last_low: float | None = None
    num_low: int = 0

    for time, voltage in samples:
        if voltage < threshold:
            num_low += 1
            last_low = time
            if run_start is None:
                run_start = time
        else:
            if run_start is not None and (time - last_low) > buffer: #TODO: decide how to handle
                intervals.append((run_start, last_low + buffer))
                run_start = None
                last_low = None

    if run_start is not None:
        intervals.append((run_start, last_low + buffer))

    return intervals, num_low

class BrownoutCheck(Check):

    def __init__(
        self,
        voltage_signal: str = "/Robot/SystemStats/BatteryVoltage",
        brownout_signal: str = "/Robot/SystemStats/BrownedOut",
        *,
        warn_voltage: float = 7.5,
        trailing_buffer: float = 0.1,
    ) -> None:

        self.id = f"brownout - warn at {warn_voltage}V"
        self.name = "Battery Brownout"
        self.voltage_signal = voltage_signal
        self.brownout_signal = brownout_signal
        self.required_signals = [voltage_signal, brownout_signal]
        self.warn_voltage = warn_voltage
        self.interval_buffer = warn_voltage

    def run(self, signals: dict[str, Signal]) -> CheckResult:

        if not self.applicable(signals):
            return CheckResult(
                self.id,
                self.name,
                Severity.NOT_APPLICABLE,
                f"No battery voltage log at {self.voltage_signal} or no brownout log at"
                f" {self.brownout_signal}"
            )

        v_signal = signals[self.voltage_signal]

        voltage_samples: list[tuple[float, float]] = [
            (t*1e-6, v) for t,v in zip(v_signal.timestamps, v_signal.values, strict=True)
            if isinstance(v, (int,float)) and not isinstance(v, bool)
        ]

        intervals, num_low = low_voltage_intervals(voltage_samples,
                                                   self.warn_voltage,
                                                   self.interval_buffer)

        b_signal = signals[self.brownout_signal]
        brownout_times: list[float] = [
            t * 1e-6 for t, v in zip(b_signal.timestamps, b_signal.values, strict=True)
            if v is True
        ]

        browned_out = len(brownout_times) > 0

        min_v = min((val for _, val in voltage_samples), default=float("nan"))
        details = {
            "min_voltage": round(min_v, 3),
            "warn_voltage": self.warn_voltage,
            "low_samples": num_low,
            "low_intervals": len(intervals),
            "brownout_events": len(brownout_times),
        }

        if browned_out:
            sev = Severity.FAIL
            window = (f"{brownout_times[0]:.1f}-{brownout_times[-1]:.1f}s"
                      if len(brownout_times) > 1 else f"{brownout_times[0]:.1f}s")
            summary = (f"RIO browned out {len(brownout_times)}x ({window}); "
                       f"voltage dropped to {min_v:.2f}V.")
        elif intervals:
            sev = Severity.WARNING
            summary = (f"Voltage dipped below {self.warn_voltage}V "
                       f"{len(intervals)}x (min {min_v:.2f}V) without browning out.")
        else:
            sev = Severity.OK
            summary = f"Battery healthy, min voltage {min_v:.2f}V."

        return CheckResult(self.id, self.name, sev, summary, details, intervals)
