# src/eagleeye/config.py
import os
from pathlib import Path


def _find_root(marker: str = "mise.toml") -> Path:
    '''
    locates a root directory based on a file marker known to appear in the desired root

    default marker is "mise.toml"
    '''
    for parent in Path(__file__).resolve().parents:
        if (parent / marker).exists():
            return parent
    raise RuntimeError(f"couldn't find {marker} above {__file__}")

def _resolve_logs() -> Path:
    env = os.environ.get("EAGLEEYE_LOGS")
    if env is not None:
        return Path(env)
    return _find_root() / "logs"

LOGS = _resolve_logs()
