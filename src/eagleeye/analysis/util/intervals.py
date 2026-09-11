from collections.abc import Iterable
from itertools import pairwise

from eagleeye.analysis.util.leaky_bucket import BucketSample
from eagleeye.signals import BoolSignal

# ---------------------------------------------------------------------------
# type aliases
# ---------------------------------------------------------------------------

type Interval = tuple[int, int]
type Intervals = list[Interval]


def low_intervals(
    buckets: Iterable[tuple[int, BucketSample]],
    signal_threshold: float,
    bucket_threshold: float,
    buffer: int,
) -> Intervals:

    intervals: Intervals = []
    run_start: int | None = None
    last_low: int | None = None
    last_signal: float | None = None
    bucket_tripped: bool = False

    for time, bucket_sample in buckets:
        signal = bucket_sample.signal
        bucket = bucket_sample.bucket_level

        if last_signal is None:
            last_signal = signal
            continue

        # detect potential interval, drop it if signal > threshold and bucket didn't trip
        if signal < signal_threshold:
            if run_start is None:
                run_start = time
            last_low = time
        elif bucket_tripped is False:
            run_start = None
        # extend last_low one timestamp for plotting
        elif last_signal < signal_threshold:
            last_low = time

        last_signal = signal

        if bucket > bucket_threshold:
            bucket_tripped = True
        elif run_start is None or last_low is None:
            continue
        elif (time - last_low) > buffer:
            intervals.append((run_start, last_low))
            run_start = None
            last_low = None

    if run_start is not None and last_low is not None:
        intervals.append((run_start, last_low))

    return intervals


def bool_intervals(sig: BoolSignal) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    start_interval = 0
    started = False

    for idx, timestamp_us in enumerate(sig.timestamps):
        bool_val = sig.values[idx]

        if not bool_val and started:
            result.append((start_interval, timestamp_us))
        else:
            started = True
            start_interval = timestamp_us

    return result


def clean_intervals(
    intervals: Intervals, *, merge_gap_us: int = 100000, min_duration_us: int = 0
) -> Intervals:

    if not intervals:
        return []

    merged = [intervals[0]]
    for start, end in intervals[1:]:
        ls, le = merged[-1]
        if start - le <= merge_gap_us:
            merged[-1] = (ls, max(le, end))
        else:
            merged.append((start, end))
    return [(a, b) for a, b in merged if (b - a) >= min_duration_us]


def threshold_excursions(
    timestamps: list[int], values: list[float], threshold: float, *, max_gap_s: float = 1.0
) -> tuple[float, list[tuple[int, int]]]:
    """
    zero-order-hold integration of time above threshold. samples: list[(t_seconds, value)]
    sorted by t. returns (seconds_over, intervals).
    """
    max_gap = int(max_gap_s * 1e6)
    samples = zip(timestamps, values, strict=True)
    seconds_over = 0.0
    intervals: list[tuple[int, int]] = []
    run_start = None
    last_t = None

    for (t0, v0), (t1, _) in pairwise(samples):
        last_t = t1
        gap = t1 - t0
        held = gap if gap <= max_gap else 0.0

        if v0 > threshold:
            seconds_over += held
            if run_start is None:
                run_start = t0
            if gap > max_gap:
                intervals.append((run_start, t0))
                run_start = None
        elif run_start is not None:
            intervals.append((run_start, t0))
            run_start = None

    if run_start is not None and last_t is not None:
        intervals.append((run_start, last_t))

    return seconds_over, intervals
