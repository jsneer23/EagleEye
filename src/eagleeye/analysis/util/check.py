from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import KW_ONLY, dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from eagleeye.analysis.util import Context, Interval, Intervals
    from eagleeye.plot import PlotSpec
    from eagleeye.signals import BaseSignal


# ---------------------------------------------------------------------------
# log checking utils
# ---------------------------------------------------------------------------


class Severity(Enum):
    """
    enum determining the result of the automated log checks
    """

    OK = "ok"
    WARNING = "warning"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"


type DetailValue = float | int | str

# ---------------------------------------------------------------------------
# log check and result storage
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CheckRun:
    check: Check
    result: CheckResult


@dataclass
class CheckResult:
    """
    class that holds information specific to one log check
    """

    id: str
    name: str
    severity: Severity
    summary: str
    details: Mapping[str, DetailValue] = field(
        default_factory=dict[str, DetailValue]
    )  # TODO look at this structure
    _: KW_ONLY
    warn_intervals: list[tuple[int, int]] = field(default_factory=list[tuple[int, int]])
    fail_intervals: list[tuple[int, int]] = field(default_factory=list[tuple[int, int]])

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
    """
    abstract class defining the base structure for log checks
    """

    id: str
    name: str
    required_signals: list[str]

    @abstractmethod
    def run(self, ctx: Context) -> CheckResult: ...

    def plot_spec(self, ctx: Context, result: CheckResult) -> PlotSpec | None:
        return None  # opt-in, not forced

    def applicable(self, signals: Mapping[str, BaseSignal[Any]]) -> bool:
        return all(name in signals for name in self.required_signals)


# ---------------------------------------------------------------------------
# helper functions
# ---------------------------------------------------------------------------

def us_to_s(timestamp: int) -> float:
    return timestamp  * 1e-6

def match_time_s(timestamp: int, match_span: Interval) -> float:
    return (timestamp - match_span[0]) * 1e-6


def mask[V](sig: BaseSignal[V], intervals: Intervals) -> Iterator[tuple[int, V]]:
    for lo, hi in intervals:
        yield from sig.zip_between_ts(lo, hi)
