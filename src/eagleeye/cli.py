import argparse
import tempfile
import webbrowser
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.highlighter import RegexHighlighter
from rich.theme import Theme

from eagleeye.analysis.config_loader import load_configs
from eagleeye.analysis.registry import build_checks
from eagleeye.analysis.util import (
    Check,
    CheckResult,
    CheckRun,
    Context,
    NotApplicableError,
    Severity,
)
from eagleeye.discovery import LogFiles
from eagleeye.parsers.wpilog_parser import LogParser
from eagleeye.plot import render


class NumberHighlighter(RegexHighlighter):
    base_style = "num."
    highlights = [r"(?P<number>\d+\.?\d*)"]  # noqa: RUF012


@dataclass(frozen=True)
class Args:
    event_code: str
    match_code: str
    plot: str | None


theme = Theme({"num.number": "blue"})
console = Console(highlighter=NumberHighlighter(), theme=theme, highlight=True)


def parse() -> Args:

    parser = argparse.ArgumentParser()
    parser.add_argument("event_code", help="event code ex. 2026cacac")
    parser.add_argument("match_code", help="match code ex. qm1 or f2 or p7")
    parser.add_argument("--plot", help="display plots of analyzed logs")

    ns = parser.parse_args()

    return Args(event_code=ns.event_code, match_code=ns.match_code, plot=ns.plot)


def run_all(checks: list[Check], ctx: Context) -> list[CheckRun]:

    results: list[CheckRun] = []

    for check in checks:
        try:
            result = check.run(ctx)
        except NotApplicableError as e:
            result = CheckResult(check.id, check.name, Severity.NOT_APPLICABLE, e.reason)

        results.append(CheckRun(check, result))

    return results


def main() -> None:

    args = parse()

    if len(args.event_code) < 6:
        raise ValueError(f"invalid event code {args.event_code}. must be at least 6 characters.")

    year = int(args.event_code[0:4])

    config_file = load_configs(year)
    checks = build_checks(config_file)

    avail_plots = [c.id for c in checks]

    if args.plot is not None and args.plot not in avail_plots:
        raise ValueError(f"invalid plot option {args.plot}. no check has matching id")

    wpilog_path = LogFiles.for_match(args.event_code, args.match_code).wpilogs[0]

    signals, last_log_timestamp = LogParser.from_file(wpilog_path).parse_data()
    ctx = Context(signals, last_log_timestamp)

    check_runs = run_all(checks, ctx)

    for run in check_runs:
        console.print(run.result)

        if args.plot and args.plot == run.check.id:
            spec = run.check.plot_spec(ctx, run.result)

            if spec:
                html = render(spec)
                path = Path(tempfile.mkdtemp()) / "plot.html"
                path.write_text(html, encoding="utf-8")
                webbrowser.open(path.as_uri())
