from rich.console import Console
from rich.highlighter import RegexHighlighter
from rich.theme import Theme

from src.analysis.checks.brownout import BrownoutCheck
from src.analysis.checks.camera_health import CameraHealthCheck
from src.analysis.checks.can import CanUtilizationCheck
from src.analysis.util import Check, CheckResult, Context, NotApplicableError, Severity
from src.discovery import LogFiles
from src.parsers.wpilog_parser import LogParser

CHECKS: list[Check] = [
    CanUtilizationCheck("/Robot/SystemStats/CANBus/Utilization", "rio"),
    CanUtilizationCheck("/Robot/Canivore/Canivore Bus Utilization", "canivore"),
    BrownoutCheck(),
    CameraHealthCheck(),
]

class NumberHighlighter(RegexHighlighter):
    base_style = "num."
    highlights = [r"(?P<number>\d+\.?\d*)"] # noqa: RUF012

theme = Theme({"num.number": "blue"})
console = Console(highlighter=NumberHighlighter(), theme=theme, highlight=True)

def run_all(checks: list[Check], ctx: Context) -> list[CheckResult]:

    results = []

    for check in checks:
        try:
            results.append(check.run(ctx))
        except NotApplicableError as e:
            results.append(
                CheckResult(check.id, check.name, Severity.NOT_APPLICABLE, e.reason)
            )
    return results

if __name__ == "__main__":
    '''
    main function for testing individual log checks
    '''
    import sys

    event_code = sys.argv[1]
    match_code = sys.argv[2]

    wpilog_path = LogFiles.for_match(event_code, match_code).wpilogs[0]

    signals, last_log_timestamp = LogParser(wpilog_path).parse_data()
    ctx = Context(signals, last_log_timestamp)

    checks = run_all(CHECKS, ctx)

    for check in checks:
        console.print(check)
