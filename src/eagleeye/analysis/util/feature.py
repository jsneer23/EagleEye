from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar, Protocol

from eagleeye.config.models import StrictModel
from eagleeye.errors import ConfigError

if TYPE_CHECKING:
    from rich.console import RenderableType

    from eagleeye.analysis.util.context import Context


class FeatureResult(Protocol):
    def __rich__(self) -> RenderableType: ...


class Feature[S: StrictModel, T: FeatureResult](ABC):
    id: ClassVar[str]
    source: ClassVar[str]

    def __init__(self, instance: str, signals: S, thresholds: T | None) -> None:
        self.instance = instance
        self.signals = signals
        self.thresholds = thresholds

    @abstractmethod
    def compute(self, ctx: Context) -> T: ...


class FeatureSet:
    def __init__(self) -> None:
        self._by_class: dict[type[Feature[Any, Any]], dict[str, Feature[Any, Any]]] = {}

    def add(self, feature: Feature[Any, Any]) -> None:
        cls = type(feature)
        if cls not in self._by_class:
            self._by_class[cls] = {}
        inner = self._by_class[cls]
        inner[feature.instance] = feature

    def get(self, cls: type[Feature[Any, Any]], instance: str | None = None) -> Feature[Any, Any]:
        try:
            by_instance = self._by_class[cls]
        except KeyError as e:
            raise ConfigError(
                f"feature {cls.__name__} not declared in FEATURE_REGISTRY in config/registry.py"
            ) from e
        if instance is None:
            if len(by_instance) != 1:
                raise ValueError(
                    f"config file declares {len(by_instance)} instances of {cls.__name__}; pass one"
                     " to ctx.feature()"
                )
            (only,) = by_instance.values()
            return only
        return by_instance[instance]
