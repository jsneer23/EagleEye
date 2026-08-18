import os
from dataclasses import dataclass
from pathlib import Path

from eagleeye.errors import safe

# ---------------------------------------------------------------------------
# resolve logs
# ---------------------------------------------------------------------------

def find_root(marker: str = "mise.toml") -> Path:
    '''
    locates a root directory based on a file marker known to appear in the desired root

    default marker is "mise.toml"
    '''
    for parent in Path(__file__).resolve().parents:
        if (parent / marker).exists():
            return parent
    raise RuntimeError(f"couldn't find {marker} above {__file__}")

def resolve_logs() -> Path:
    env = os.environ.get("EAGLEEYE_LOGS")
    if env is not None:
        return Path(env)
    return find_root() / "logs"

_LOGS = resolve_logs()

# ---------------------------------------------------------------------------
# log filestructure handling / logfile discovery
# ---------------------------------------------------------------------------

def match_dir(event_code: str, match_code: str) -> Path:
    '''
    find file path to match logs given an event code and a match code, if one exists
    '''
    p = (_LOGS / event_code / match_code).resolve()
    if not p.is_relative_to(_LOGS.resolve()):
        raise ValueError(f"illegal input: {safe(event_code)}/{safe(match_code)}")
    return p

@dataclass
class LogFiles:
    '''
    log files management dataclass
    '''
    dir: Path

    @classmethod
    def for_match(cls, event: str, match: str) -> "LogFiles":
        return cls(match_dir(event, match))

    @property
    def wpilogs(self) -> list[Path]:
        return sorted(self.dir.glob("*.wpilog"))

    @property
    def hoot(self) -> list[Path]:
        return sorted(self.dir.glob("*.hoot"))
