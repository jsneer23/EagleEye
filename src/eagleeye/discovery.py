from dataclasses import dataclass
from pathlib import Path

from eagleeye.config import LOGS
from eagleeye.errors import safe


# ---------------------------------------------------------------------------
# log filestructure handling / logfile discovery
# ---------------------------------------------------------------------------
def match_dir(event_code: str, match_code: str) -> Path:
    '''
    find file path to match logs given an event code and a match code, if one exists
    '''
    p = (LOGS / event_code / match_code).resolve()
    if not p.is_relative_to(LOGS.resolve()):
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
