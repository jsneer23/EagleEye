import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from eagleeye.discovery import find_root
from eagleeye.errors import ConfigError

MAX_CONFIG_BYTES = 256 * 1024

# ---------------------------------------------------------------------------
# resolve config
# ---------------------------------------------------------------------------

def resolve_config_path() -> Path:
    env = os.environ.get("EAGLEEYE_CONFIG")
    if env is not None:
        return Path(env)
    return find_root() / "analysis"

# ---------------------------------------------------------------------------
# pydantic config checker
# ---------------------------------------------------------------------------

class ConfigFile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: int = 1
    configs: dict[str, dict[str, Any]] = Field(default_factory=dict)

# ---------------------------------------------------------------------------
# load and parse configs
# ---------------------------------------------------------------------------

def parse_configs(text: str, *, source: str = "<memory>") -> ConfigFile:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ConfigError(f"{source}: invalid JSON ({e.msg} at line {e.lineno})") from e

    try:
        return ConfigFile.model_validate(data)
    except ValidationError as e:
        raise ConfigError(f"{source}: {e}") from e

def load_configs(year: int) -> ConfigFile:
    path = resolve_config_path() / f"{year}.json"
    try:
        raw = path.read_bytes()
    except OSError as e:
        raise ConfigError(f"could not read {path}: {e}") from e

    if len(raw) > MAX_CONFIG_BYTES:
        raise ConfigError(f"{path}: config exceeds {MAX_CONFIG_BYTES} bytes")

    return parse_configs(raw.decode("utf-8"), source=str(path))
