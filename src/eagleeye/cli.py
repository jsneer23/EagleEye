import sys

from rich.console import Console
from rich.highlighter import RegexHighlighter
from rich.theme import Theme

from eagleeye.analysis.config_loader import load_configs
from eagleeye.analysis.registry import build_checks
from eagleeye.analysis.util import Check, CheckResult, Context, NotApplicableError, Severity
from eagleeye.discovery import LogFiles
from eagleeye.parsers.wpilog_parser import LogParser


class NumberHighlighter(RegexHighlighter):
    base_style = "num."
    highlights = [r"(?P<number>\d+\.?\d*)"] # noqa: RUF012

theme = Theme({"num.number": "blue"})
console = Console(highlighter=NumberHighlighter(), theme=theme, highlight=True)

def run_all(checks: list[Check], ctx: Context) -> list[CheckResult]:

    results: list[CheckResult] = []

    for check in checks:
        try:
            results.append(check.run(ctx))
        except NotApplicableError as e:
            results.append(
                CheckResult(check.id, check.name, Severity.NOT_APPLICABLE, e.reason)
            )
    return results


def main() -> None:
    event_code = sys.argv[1]
    match_code = sys.argv[2]

    if len(event_code) < 6:
        raise ValueError("invalid event code {event_code}. must be at least 6 characters.")

    year = int(event_code[0:4])

    wpilog_path = LogFiles.for_match(event_code, match_code).wpilogs[0]

    signals, last_log_timestamp = LogParser.from_file(wpilog_path).parse_data()
    ctx = Context(signals, last_log_timestamp)

    config_file = load_configs(year)

    checks = build_checks(config_file)
    checks = run_all(checks, ctx)

    for check in checks:
        console.print(check)



