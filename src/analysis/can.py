from collections.abc import Mapping
from itertools import pairwise

from src.analysis.util import Check, CheckResult, Severity
from src.parsers.util import BaseSignal, FloatSignal

# ---------------------------------------------------------------------------
# helper functions
# ---------------------------------------------------------------------------

def threshold_excursions(samples: list[tuple[float,float]], threshold: float, *,
                         max_gap_s: float=1.0) -> tuple[float, list[tuple[float, float]]]:
    """
    Zero-order-hold integration of time above threshold. samples: list[(t_seconds, value)]
    sorted by t. Returns (seconds_over, intervals).
    """

    seconds_over = 0.0
    intervals: list[tuple[float, float]] = []
    run_start = None

    for (t0, v0), (t1, _) in pairwise(samples):

        gap = t1 - t0
        held = gap if gap <= max_gap_s else 0.0

        if v0 > threshold:
            seconds_over += held
            if run_start is None:
                run_start = t0
            if gap > max_gap_s:
                intervals.append((run_start, t0))
                run_start = None
        elif run_start is not None:
            intervals.append((run_start, t0))
            run_start = None

    if run_start is not None:
        intervals.append((run_start, samples[-1][0]))

    return seconds_over, intervals

def clean_intervals(intervals: list[tuple[float, float]], *, merge_gap_s: float = 0.1,
                    min_duration_s: float =0.0) -> list[tuple[float, float]]:

    if not intervals:
        return []

    merged = [intervals[0]]
    for start, end in intervals[1:]:
        ls, le = merged[-1]
        if start - le <= merge_gap_s:
            merged[-1] = (ls, max(le, end))
        else:
            merged.append((start, end))
    return [(a, b) for a, b in merged if (b - a) >= min_duration_s]

class CanUtilizationCheck(Check):

    def __init__(
        self,
        signal_name: str,
        bus_label: str,
        *,
        warn: float = 0.80,
        warn_peak: float = 0.95,
        sustained: float = 0.5
    ) -> None:

        self.id = f"can_util::{bus_label}"
        self.name = f"CAN Utilization - {bus_label}"
        self.required_signals = [signal_name]
        self.signal_name = signal_name
        self.bus_label = bus_label
        self.warn = warn
        self.warn_peak = warn_peak
        self.sustained = sustained

    def run(self, signals: Mapping[str, BaseSignal]) -> CheckResult:

        if not self.applicable(signals):
            return CheckResult(
                self.id,
                self.name,
                Severity.NOT_APPLICABLE,
                f"No can utilization found for {self.bus_label}"
            )

        signal = signals[self.signal_name]

        if not isinstance(signal, FloatSignal):
            return CheckResult(self.id, self.name, Severity.NOT_APPLICABLE,
                           f"{self.signal_name} is not a float")

        samples: list[tuple[float,float]] = [
            (t*1e-6, v) for t,v in zip(signal.timestamps, signal.values, strict=True)
            if isinstance(v, (int,float)) and not isinstance(v, bool)
        ]

        if len(samples) < 2:
            return CheckResult(self.id,
                self.name,
                Severity.NOT_APPLICABLE,
                f"Too few samples for {self.bus_label}."
                )

        peak = max(v for _,v in samples)
        mean = sum(v for _,v in samples) / len(samples)
        seconds_over, raw = threshold_excursions(samples, self.warn)
        intervals = clean_intervals(raw, min_duration_s=0.1)
        longest = max((b-a for a,b in intervals), default=0.0)

        details = {
            "peak": round(peak, 4), "mean": round(mean, 4),
            "warn_threshold": self.warn,
            "seconds_over_warn": round(seconds_over, 3),
            "longest_excursion_s": round(longest, 3),
            "samples": len(samples),
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
