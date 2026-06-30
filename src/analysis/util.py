from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum

from src.parsers.util import BaseSignal

# ---------------------------------------------------------------------------
# analysis utils
# ---------------------------------------------------------------------------

class Severity(Enum):
    '''
    enum determining the result of the automated log checks
    '''
    OK = "ok"
    WARNING = "warning"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"

@dataclass
class CheckResult:
    '''
    class that holds information specific to one log check
    '''
    id: str
    name: str
    severity: Severity
    summary: str
    details: dict[str, float | int | str] = field(default_factory=dict)
    intervals: list[tuple[float, float]] = field(default_factory=list)

    def __str__(self) -> str:
        return f"[{self.severity.value.upper()}] {self.name}: {self.summary}"

class Check(ABC):
    '''
    abstract class defining the base structure for log checks
    '''
    id: str
    name: str
    required_signals: list[str]

    @abstractmethod
    def run(self, signals: Mapping[str, BaseSignal]) -> CheckResult:
        ...

    def applicable(self, signals: Mapping[str, BaseSignal]) -> bool:
        return all(name in signals for name in self.required_signals)
