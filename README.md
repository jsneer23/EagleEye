# EagleEye - an FRC Log Review Tool

[![CI](https://github.com/jsneer23/EagleEye/actions/workflows/ci.yml/badge.svg)](https://github.com/jsneer23/EagleEye/actions/workflows/ci.yml)
[![codecov](https://codecov.io/github/jsneer23/EagleEye/graph/badge.svg?token=8I0JF8M52O)](https://codecov.io/github/jsneer23/EagleEye)

A Python toolkit for analyzing robot log files (WPILib `.wpilog`, or CTRE `.hoot`, etc.).

## Prerequisites

You need two tools installed: **uv** (manages Python and dependencies) and
**mise** (runs project tasks). Install both with:

**macOS / Linux:**

    curl -LsSf https://astral.sh/uv/install.sh | sh
    curl https://mise.run | sh

**macOS with Homebrew** (if you already use `brew`):

    brew install uv mise

**Windows:** see the [uv](https://docs.astral.sh/uv/getting-started/installation/)
and [mise](https://mise.jdx.dev/getting-started.html) install pages.

After installing, restart your terminal, then confirm both work:

    uv --version
    mise --version

## Setup

1. Install `uv` and `mise` (see above).
2. Clone and enter the repo:

       git clone https://github.com/jsneer23/EagleEye.git
       cd EagleEye

3. Build the environment:

       mise run setup

4. Open in VS Code and click **"Install recommended extensions"** when prompted.

Note: You shouldn't need to activate the virtual environment — `uv run` and the `mise`
tasks manage it for you.

## Usage

Match logs live under `logs/{event_code}/{match_number}/`. For example,
Qualification Match 1 from the 2026 Contra Costa District Event goes in `logs/2026cacac/qm1/`.

Run the analysis on a match using mise as follows:

    mise run analyze 2026cacac qm1


## Development

Run these via mise:

| Command | What it does |
| --- | --- |
| `mise run test` | Run the test suite |
| `mise run lint` | Ruff lint check |
| `mise run format` | Ruff formatter |
| `mise run fix` | Auto-fix ruff lint issues |
| `mise run typecheck` | Pyright type check |
| `mise run checks` | Pre-commit checks (lint, type check, and tests) |
| `mise run analyze <event> <match>` | Analyze logs for `<match>` at `<event>` |

## Project layout

    src/eagleeye/
    ├── cli.py            # command-line entry point (main)
    ├── config.py         # where logs live (env-configurable)
    ├── discovery.py      # finding a match's files
    ├── wpilog_parser.py  # decodes the .wpilog binary format
    ├── util.py           # byte-reading helpers + signal types
    └── analysis/checks/  # the individual checks (CAN, brownout, cameras)

    tests/                # mirrors src/ — test_<module>.py

## Adding a new check

1. Create `src/eagleeye/analysis/checks/your_check.py`.
2. Follow the existing pattern (see `brownout.py`): implement `run(ctx)`
   returning a `CheckResult`.
3. Register it in the `CHECKS` list.
4. Add a test at `tests/analysis/checks/test_your_check.py`.
5. Run `mise run checks` and `mise run test` to confirm everything passes.

## License

MIT