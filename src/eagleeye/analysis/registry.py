from collections.abc import Callable, Sequence
from typing import Any, Protocol, Self

from pydantic import BaseModel

from eagleeye.analysis.checks import (
    BrownoutCheck,
    BrownoutJSON,
    CameraHealthCheck,
    CameraHealthJSON,
    CanUtilizationCheck,
    CanUtilJSON,
    RadioCheck,
    RadioJSON,
)
from eagleeye.analysis.config_loader import ConfigFile
from eagleeye.analysis.util import Check
from eagleeye.errors import ConfigError


class ConfigSection(Protocol):
    @classmethod
    def model_validate(cls, obj: Any) -> Self:  # noqa: ANN401
        ...
    def build(self) -> Sequence[BaseModel]: ...


CheckFactory = Callable[[Any], Check]

REGISTRY: dict[str, tuple[type[ConfigSection], CheckFactory]] = {
    "brownout": (BrownoutJSON, BrownoutCheck.from_config),
    "radio": (RadioJSON, RadioCheck.from_config),
    "can_util": (CanUtilJSON, CanUtilizationCheck.from_config),
    "camera_health": (CameraHealthJSON, CameraHealthCheck.from_config),
}


def build_checks(file: ConfigFile) -> list[Check]:

    configs = file.configs
    unknown = configs.keys() - REGISTRY.keys()

    if unknown:
        raise ConfigError(
            f"unknown check ids: {sorted(unknown)}. ensure all checks declared in config json file"
            " are also declared in the log check registry in /src/eagleeye/analysis/registry.py"
        )

    checks: list[Check] = []
    for check_id, (model, factory) in REGISTRY.items():
        section = model.model_validate(configs.get(check_id, {}))
        checks.extend(factory(cfg) for cfg in section.build())
    return checks
