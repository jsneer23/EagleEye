import struct
from contextlib import suppress

import pytest

from eagleeye.errors import LogError, LogFormatError, PayloadError
from eagleeye.parsers.wpilog_parser import LogParser
from eagleeye.signals import FloatSignal

from .wpilog_builder import control, finish, log, record, start, update

DOUBLE = "double"

def d(value: float) -> bytes:
    return struct.pack("<d", value)

# ---------------------------------------------------------------------------
# positive checks
# ---------------------------------------------------------------------------

def test_single_signal_accumulates_samples() -> None:
    buf = log(
        control(start(1, "/voltage", DOUBLE)),
        record(1, 1000, d(12.5)),
        record(1, 2000, d(12.0)),
    )
    signals, last_ts = LogParser(buf).parse_data()

    assert set(signals) == {"/voltage"}
    sig = signals["/voltage"]
    assert isinstance(sig, FloatSignal)
    assert sig.timestamps == [1000, 2000]
    assert sig.values == [12.5, 12.0]
    assert last_ts == 2000

def test_interleaved_entries_do_not_cross_contaminate() -> None:
    buf = log(
        control(start(1, "/a", DOUBLE)),
        control(start(2, "/b", DOUBLE)),
        record(1, 100, d(1.0)),
        record(2, 200, d(2.0)),
        record(1, 300, d(3.0)),
    )
    signals, _ = LogParser(buf).parse_data()

    assert signals["/a"].values == [1.0, 3.0]
    assert signals["/b"].values == [2.0]

def test_last_timestamp_is_max_not_last_seen() -> None:
    buf = log(
        control(start(1, "/a", DOUBLE)),
        record(1, 5000, d(1.0)),
        record(1, 100, d(2.0)),  # out of order
    )
    _, last_ts = LogParser(buf).parse_data()
    assert last_ts == 5000

def test_empty_log() -> None:
    signals, last_ts = LogParser(log()).parse_data()
    assert signals == {}
    assert last_ts == 0

def test_extra_header_is_skipped() -> None:
    buf = log(
        control(start(1, "/a", DOUBLE)),
        record(1, 100, d(1.0)),
        extra_header=b'{"source":"test"}',
    )
    signals, _ = LogParser(buf).parse_data()
    assert signals["/a"].values == [1.0]

def test_multibyte_headers() -> None:
    '''
    test entry_id and timestamp header fields can be more than one byte
    '''
    buf = log(
        control(start(300, "/a", DOUBLE)),
        record(300, 2**40, d(1.0)),
    )
    signals, last_ts = LogParser(buf).parse_data()
    assert signals["/a"].values == [1.0]
    assert last_ts == 2**40

def test_data_after_finish_is_still_accepted() -> None:
    '''
    entries are deliberately not popped on finish — records may be out of order
    '''
    buf = log(
        control(start(1, "/a", DOUBLE)),
        record(1, 100, d(1.0)),
        control(finish(1)),
        record(1, 200, d(2.0)),
    )
    signals, _ = LogParser(buf).parse_data()
    assert signals["/a"].values == [1.0, 2.0]

def test_metadata_update_applies() -> None:
    buf = log(
        control(start(1, "/a", DOUBLE)),
        control(update(1, "{}")),
        record(1, 100, d(1.0)),
    )
    LogParser(buf).parse_data()  # no raise

# ---------------------------------------------------------------------------
# negative checks
# ---------------------------------------------------------------------------

def test_undeclared_entry_id_raises() -> None:
    buf = log(record(7, 100, d(1.0)))
    with pytest.raises(LogFormatError, match="7"):
        LogParser(buf).parse_data()

def test_payload_too_short_for_declared_type_raises() -> None:
    buf = log(
        control(start(1, "/a", DOUBLE)),
        record(1, 100, b"\x00\x00\x00\x00"),  # 4 bytes for a double
    )
    with pytest.raises(PayloadError):
        LogParser(buf).parse_data()

def test_record_overruns_buffer_raises() -> None:
    buf = log(
        control(start(1, "/a", DOUBLE)),
        record(1, 100, d(1.0)),
    )
    with pytest.raises(LogFormatError):
        LogParser(buf[:-3]).parse_data()

# ---------------------------------------------------------------------------
# truncation error checks
# ---------------------------------------------------------------------------

GOOD = log(
    control(start(1, "/a", DOUBLE)),
    control(start(2, "/b", "int64")),
    record(1, 100, d(1.0)),
    record(2, 200, struct.pack("<q", 7)),
    record(1, 300, d(2.0)),
)

@pytest.mark.parametrize("n", range(1, len(GOOD)))
def test_truncation_doesnt_raise_unexpected_error(n: int) -> None:
    with suppress(LogError):
        LogParser(GOOD[:n]).parse_data()
