from collections.abc import Iterable
from dataclasses import dataclass

from eagleeye.signals import TimeSeries


@dataclass(frozen=True, slots=True)
class BucketSample:
    signal: float
    bucket_level: float


def leaky_bucket(
    samples: Iterable[tuple[int, float]],
    threshold: float,
) -> TimeSeries[BucketSample]:

    bucket = 0.0
    last_time = None

    dt_cap = 40000  # 40ms max interval - don't overcount large loop overruns
    max_bucket = 50000
    leak_rate = 1

    times: list[int] = []
    buckets: list[BucketSample] = []

    for time, voltage in samples:
        if last_time is None:
            last_time = time
            continue

        deficit = threshold - voltage

        dt = min(time - last_time, dt_cap)
        dt = max(0, dt)  # protect against bad input file

        last_time = time

        if deficit > 0:
            bucket += dt * deficit

        else:
            bucket += dt * deficit * leak_rate

        bucket = max(bucket, 0)
        bucket = min(bucket, max_bucket)

        times.append(time)
        buckets.append(BucketSample(signal=voltage, bucket_level=bucket))

    return TimeSeries[BucketSample](name="brownout_bucket", timestamps_us=times, values=buckets)
