from rich.console import Console
from rich.highlighter import RegexHighlighter
from rich.theme import Theme

from src.analysis.util import CheckResult, Severity


class NumberHighlighter(RegexHighlighter):
    base_style = "num."
    highlights = [r"(?P<number>\d+\.?\d*)"] # noqa: RUF012

theme = Theme({"num.number": "blue"})
console = Console(highlighter=NumberHighlighter(), theme=theme, highlight=True)

def print_to_terminal(result: CheckResult) -> None:
    severity: str = result.severity.value
    if result.severity == Severity.FAIL:
        severity = f"[[red]{severity}[/red]]"
    elif result.severity == Severity.WARNING:
        severity = f"[[orange3]{severity}[/orange3]]"
    elif result.severity == Severity.OK:
        severity = f"[[green]{severity}[/green]]"
    else:
        severity = f"[[orange3]{severity}[/orange3]]"

    console.print(f"{severity} {result.name}: {result.summary}")
