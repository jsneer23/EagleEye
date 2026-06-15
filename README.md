# FRC Log Review Tool

A Python toolkit for analysing WPILib `.wpilog` robot log files.  
Built to run game-agnostic health checks as well as robot specific 
function checks and system analysis.

Eventually this will have web-based log uploading, reivew, and and AI-assisted analysis.

---

## Files

| File | Purpose |
|---|---|
| `wpilog_reader.py` | Low-level `.wpilog` binary parser |
| `log_checks.py` | All health-check functions + `run_all_checks()` + `format_report()` |
| `system_checks_YYYY.py` | All subsystem specific checks for a specific robot+ `run_all_checks()` + `format_report()` |
| `frc_log_review.py` | CLI entry point |

---

## Quick Start

```bash
# Full check with details
python frc_log_review.py FRC_20260403.wpilog -v

# Concise summary table
python frc_log_review.py FRC_20260403.wpilog

# List every channel in a log
python frc_log_review.py FRC_20260403.wpilog --channels

# Search for specific channels
python frc_log_review.py FRC_20260403.wpilog --search voltage
python frc_log_review.py FRC_20260403.wpilog --search swerve

# Run only specific checks
python frc_log_review.py FRC_20260403.wpilog --run can_dropout,voltage_sag -v
```

---

## Annual Health Checks

| # | Check | What it looks for |
|---|---|---|
| 1 | **CAN Bus Dropout** | OffCount > 0, rising error counts, gaps in utilisation signal while enabled |
| 2 | **CAN Bus Utilisation** | Sustained utilisation > 80% (warn) / 90% (error) — prefers Canivore bus |
| 3 | **Voltage Sag / Brownout** | BrownedOut flag set, voltage < 7 V, or voltage within 0.5 V of brownout threshold |
| 4 | **Battery Health** | Resting voltage in the first 15 s < 12.5 V (warn) / 12.0 V (error) |
| 5 | **Motor Stall** | High stator current + near-zero velocity for ≥ 250 ms across all logged motors |
| 6 | **Odometry Drift** | Vision-pose vs odometry comparison during enabled play (> 30 cm warn / 60 cm error) |
| 7 | **Camera Disconnect** | Any camera connection dropped for > 100 ms |
| 8 | **April Tag Detection** | Per-camera target-seen rate while enabled (< 10% warn / < 2% error) |
| 9 | **Swerve Module Heading** | Per-module mean heading error vs target (> 5°) and outlier detection |

---

## Using as a Library

```python
from wpilog_reader import DataLogReader
from log_checks import run_all_checks, format_report

reader = DataLogReader("FRC_20260403.wpilog")

# Browse all channels
for info in reader.list_channels("canivore"):
    print(info.entry_id, info.dtype, info.name)

# Read a specific channel — returns list[(timestamp_sec, value)]
voltage = reader.read_channel("/Robot/SystemStats/BatteryVoltage")
for ts, v in voltage[:5]:
    print(f"t={ts:.3f}s  {v:.3f} V")

# Read multiple channels in one pass (fast)
data = reader.read_channels([
    "/Robot/SystemStats/BatteryVoltage",
    "/Robot/SystemStats/BatteryCurrent",
    "/Robot/SystemStats/CANBus/Utilization",
])

# Run all health checks
results = run_all_checks(reader)
print(format_report(results, verbose=True))

# Or just one check
from log_checks import check_voltage_sag
result = check_voltage_sag(reader)
print(result.severity, result.summary)
for detail in result.details:
    print(" •", detail)
```

---

## Adding Year-Specific Checks

Add a new function to `log_checks.py` (or a separate file, e.g. `checks_2026.py`)
following the same pattern, then add it to `ALL_CHECKS`:

```python
# In log_checks.py  (or checks_2026.py)
def check_coral_score(reader: DataLogReader) -> CheckResult:
    name = "Coral Scoring"
    _, data = _first(reader, "/Robot/CoralArm/AtGoal")
    if not data:
        return _missing(name, "/Robot/CoralArm/AtGoal channel not found")
    ...
    return CheckResult(name=name, passed=True, severity="ok", summary="...")

# Then register it:
ALL_CHECKS.append(check_coral_score)
```

---

## CheckResult fields

```python
@dataclass
class CheckResult:
    name: str            # human label
    passed: bool | None  # None = data unavailable
    severity: str        # "ok" | "warn" | "error" | "missing"
    summary: str         # one-liner for a table
    details: list[str]   # bullet-point details (verbose mode)
    data: list[tuple[float, Any]]   # raw (timestamp_sec, value) for plotting
```

---

## Road Map toward the Web Frontend

The library is structured with that future in mind:

- **`wpilog_reader.py`** — pure parsing, no I/O side-effects; can be wrapped
  by a FastAPI/Flask route that accepts an uploaded `.wpilog` and returns JSON.
- **`log_checks.py`** — `CheckResult` is a dataclass that serialises cleanly
  to JSON via `dataclasses.asdict()`.  The `data` field carries the raw
  timeseries for charting.
- **Future: battery tracking** — attach battery ID metadata to the reader
  (filename, FMSInfo channels, or a separate YAML manifest) and aggregate
  `check_battery_health` results across matches.
- **Future: AI agent** — the structured `CheckResult` output + raw channel
  data are a good input to an LLM-based Q&A layer (e.g. via the
  `wpilog-mcp` MCP server pattern).
