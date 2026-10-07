from collections.abc import Mapping
from typing import Any, cast

from rich.console import Console

from eagleeye.analysis.util.feature import Feature, FeatureResult, FeatureSet
from eagleeye.config.models import StrictModel
from eagleeye.errors import NotApplicableError
from eagleeye.signals import BaseSignal


# ---------------------------------------------------------------------------
# log context utils
# --------------------------------------------------------------------------
class Context:
    def __init__(
        self, signals: Mapping[str, BaseSignal[Any]], features: FeatureSet, last_log_timestamp: int
    ) -> None:
        self.signals = signals
        self._features = features
        self._feature_cache: dict[Feature[Any, FeatureResult], FeatureResult] = {}
        self.last_log_timestamp = last_log_timestamp

    def print_features(self, console: Console) -> None:
        for result in self._feature_cache.values():
            console.print(result)

    def feature[S: StrictModel, T: FeatureResult](
        self, cls: type[Feature[S, T]], instance: str | None = None
    ) -> T:
        feature = self._features.get(cls, instance)
        if feature not in self._feature_cache:
            self._feature_cache[feature] = feature.compute(self)

        # notice that you can't define the featue cache above like follows
        #   self._feature_cache: dict[Feature[Any, T], T]
        # because pyright will assume the dict is the SAME type T in every entry.
        # thus, you must leave this as a base type FeatureResult in the dict definition
        # and cast using the known type T from the function call before returning
        # this works because the only writes to the cache occur here so you can guarantee
        # the type
        return cast("T", self._feature_cache[feature])

    def require[S: BaseSignal[Any]](self, name: str, kind: type[S]) -> S:
        sig = self.signals.get(name)
        if sig is None:
            raise NotApplicableError(f"{name} is missing from log")
        elif not isinstance(sig, kind):
            raise NotApplicableError(f"{name} is type {sig.__name__} not type {kind.__name__}")
        return sig
