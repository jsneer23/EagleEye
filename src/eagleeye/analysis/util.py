from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from itertools import pairwise
from typing import TYPE_CHECKING, Any, ClassVar, Protocol, cast

from eagleeye.parsers.signals import BaseSignal

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from rich.console import Console, RenderableType

# ---------------------------------------------------------------------------
# type aliases
# ---------------------------------------------------------------------------

type Interval = tuple[int, int]
type Intervals = list[Interval]

# ---------------------------------------------------------------------------
# log context utils
# ---------------------------------------------------------------------------

class Context:
    def __init__(self, signals: Mapping[str, BaseSignal[Any]], last_log_timestamp: int) -> None:
        self.signals = signals
        self._feature_cache: dict[str, FeatureResult] = {}
        self.last_log_timestamp = last_log_timestamp

    def print_features(self, console: Console) -> None:
        for result in self._feature_cache.values():
            console.print(result)

    def feature[T: FeatureResult](self, feat: Feature[T]) -> T:
        if feat.key not in self._feature_cache:
            self._feature_cache[feat.key] = feat.compute(self)
        return cast("T", self._feature_cache[feat.key])

    def require[S: BaseSignal[Any]](self, name: str, kind: type[S]) -> S:
        sig = self.signals.get(name)
        if sig is None:
            raise NotApplicableError(f"{name} is missing from log")
        elif not isinstance(sig, kind):
            raise NotApplicableError(f"{name} is type {sig.__name__} not type {kind.__name__}")
        return sig

class FeatureResult(Protocol):
    def __rich__(self) -> RenderableType: ...

class Feature[T: FeatureResult](ABC):
    key: ClassVar[str]

    @abstractmethod
    def compute(self, ctx: Context) -> T: ...

# ---------------------------------------------------------------------------
# log checking utils
# ---------------------------------------------------------------------------

class Severity(Enum):
    '''
    enum determining the result of the automated log checks
    '''
    OK = "ok"
    WARNING = "warning"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"

class NotApplicableError(Exception):
    '''
    throw error when data missing or mismatched so we only have to handle
    creating a Severity.NOT_APPLICABLE once
    '''
    def __init__(self, reason: str) -> None:
        self.reason = reason

type DetailValue = float | int | str

@dataclass
class CheckResult:
    '''
    class that holds information specific to one log check
    '''
    id: str
    name: str
    severity: Severity
    summary: str
    details: Mapping[str, DetailValue] = field(default_factory=dict[str, DetailValue]) #TODO look at this structure #noqa:E501
    intervals: list[tuple[float, float]] = field(default_factory=list[tuple[float, float]])

    def __str__(self) -> str:
        return f"[{self.severity.value.upper()}] {self.name}: {self.summary}"

    def __rich__(self) -> str:
        severity = self.severity.value

        if self.severity == Severity.FAIL:
            severity = f"[[red]{severity}[/red]]"
        elif self.severity == Severity.WARNING:
            severity = f"[[orange3]{severity}[/orange3]]"
        elif self.severity == Severity.OK:
            severity = f"[[green]{severity}[/green]]"
        else:
            severity = f"[[orange3]{severity}[/orange3]]"

        return f"{severity} {self.name}: {self.summary}"

class Check(ABC):
    '''
    abstract class defining the base structure for log checks
    '''
    id: str
    name: str
    required_signals: list[str]

    @abstractmethod
    def run(self, ctx: Context) -> CheckResult:
        ...

    def applicable(self, signals: Mapping[str, BaseSignal[Any]]) -> bool:
        return all(name in signals for name in self.required_signals)

# ---------------------------------------------------------------------------
# helper functions
# ---------------------------------------------------------------------------

def us_to_s(timestamp: int, match_span: Interval) -> float:
    return (timestamp - match_span[0]) * 1e-6

def mask[V](sig: BaseSignal[V], intervals: Intervals) -> Iterator[tuple[int, V]]:
    for lo, hi in intervals:
        yield from sig.zip_between_ts(lo, hi)

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

def threshold_excursions(timestamps: list[int],
                         values: list[float],
                         threshold: float, *,
                         max_gap_s: float=1.0) -> tuple[float, list[tuple[float, float]]]:
    """
    Zero-order-hold integration of time above threshold. samples: list[(t_seconds, value)]
    sorted by t. Returns (seconds_over, intervals).
    """
    samples = zip(timestamps, values, strict=True)
    seconds_over = 0.0
    intervals: list[tuple[float, float]] = []
    run_start = None
    last_t = None

    for (t0, v0), (t1, _) in pairwise(samples):

        last_t = t1
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

    if run_start is not None and last_t is not None:
        intervals.append((run_start, last_t))

    return seconds_over, intervals
