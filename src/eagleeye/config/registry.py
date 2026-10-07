from typing import Any

from pydantic import ValidationError

from eagleeye.analysis.checks import (
    BrownoutCheck,
    # CameraHealthCheck,
    CanUtilCheck,
    RadioCheck,
)
from eagleeye.analysis.features import RADIO_JSON, ROBOT_PHASES
from eagleeye.analysis.util import Check, Feature, FeatureSet
from eagleeye.config.models import CheckConfig, Config, Source, StrictModel
from eagleeye.errors import ConfigError

CHECK_REGISTRY: tuple[type[Check[Any, Any]], ...] = (
    BrownoutCheck,
    RadioCheck,
    CanUtilCheck,
    # CameraHealthCheck,
)

FEATURE_REGISTRY: tuple[type[Feature[Any, Any]], ...] = (RADIO_JSON, ROBOT_PHASES)


def build_checks(config: Config) -> list[Check[Any, Any]]:

    checks: list[Check[Any, Any]] = []

    for cls in CHECK_REGISTRY:
        check_cfg: CheckConfig[StrictModel] | None = getattr(config.thresholds, cls.id)

        if check_cfg is None:
            continue

        source: Source[StrictModel] = getattr(config.sources, cls.source)

        unknown = set(check_cfg.overrides) - set(source.instances)
        if unknown:
            raise ConfigError(
                f"{cls.id}: overrides for unknown instances {sorted(unknown)} "
                f"(known: {sorted(source.instances)})"
            )

        for instance, signals in source.instances.items():
            try:
                thresholds = check_cfg.resolve(instance)
            except ValidationError as e:
                raise ConfigError(f"{cls.id}.{instance}: {e}") from None
            checks.append(cls(instance, signals, thresholds))

    return checks


def build_features(config: Config) -> FeatureSet:

    features = FeatureSet()

    for cls in FEATURE_REGISTRY:
        # check_cfg: CheckConfig[StrictModel] | None = getattr(config.thresholds, cls.id)

        # if check_cfg is None:
        #    continue

        source: Source[StrictModel] = getattr(config.sources, cls.source)

        # unknown = set(check_cfg.overrides) - set(source.instances)
        # if unknown:
        #    raise ConfigError(
        #        f"{cls.id}: overrides for unknown instances {sorted(unknown)} "
        #        f"(known: {sorted(source.instances)})"
        #    )

        for instance, signals in source.instances.items():
            # try:
            #    thresholds = check_cfg.resolve(instance)
            # except ValidationError as e:
            #    raise ConfigError(f"{cls.id}.{instance}: {e}") from None
            # features.add(cls(instance, signals, thresholds))

            features.add(cls(instance, signals, None))

    return features
