# ---------------------------------------------------------------------------
# error handling classes
# ---------------------------------------------------------------------------
class LogError(Exception):
    public = "the log file could not be parsed."

    def __init__(self, detail: str, *, public: str | None = None) -> None:
        super().__init__(detail)          # diagnostic — logs only
        if public is not None:
            self.public = public

class LogFormatError(LogError):
    public = "the log structure is invalid."

class PayloadError(LogError):
    public = "a data record in the log was malformed."

class SchemaError(LogError):
    public = "there was an error decoding a log schema"

class ConfigError(LogError):
    public = "there was an error decoding a check config"

def safe(s: str, limit: int = 64) -> str:
    return repr(s[:limit] + "…" if len(s) > limit else s)
