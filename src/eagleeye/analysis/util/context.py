from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar, Protocol, cast

from eagleeye.signals import BaseSignal

if TYPE_CHECKING:
    from collections.abc import Mapping

    from rich.console import Console, RenderableType


# ---------------------------------------------------------------------------
# log context utils
# ---------------------------------------------------------------------------
class NotApplicableError(Exception):
    """
    throw error when data missing or mismatched so we only have to handle
    creating a Severity.NOT_APPLICABLE once
    """

    def __init__(self, reason: str) -> None:
        self.reason = reason


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
