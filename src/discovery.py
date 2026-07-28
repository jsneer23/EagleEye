from dataclasses import dataclass
from pathlib import Path

from .config import LOGS


# ---------------------------------------------------------------------------
# log filestructure handling / logfile discovery
# ---------------------------------------------------------------------------
def match_dir(event: str, match: str) -> Path:
    p = (LOGS / event / match).resolve()
    if not p.is_relative_to(LOGS.resolve()):
        raise ValueError(f"illegal input: {event}/{match}")
    return p

@dataclass
class LogFiles:
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
