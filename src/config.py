# src/eagleeye/config.py
import os
from pathlib import Path


def _find_root(marker: str = "mise.toml") -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / marker).exists():
            return parent
    raise RuntimeError(f"couldn't find {marker} above {__file__}")

LOGS = Path(os.environ.get("EAGLEEYE_LOGS", _find_root() / "logs"))
