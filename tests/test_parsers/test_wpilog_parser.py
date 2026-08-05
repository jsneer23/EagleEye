import re
import struct
from pathlib import Path
from typing import Any

import pytest

from eagleeye.errors import LogFormatError
from eagleeye.parsers.wpilog_parser import (
    MAGIC,
    VERSION,
    LogParser,
    apply_control_record,
    apply_data_record,
    decode_header_bitfield,
    parse_wpilog_header,
    read_finish_record,
    read_record,
    read_record_header,
    read_start_record,
    update_metadata_record,
)
from eagleeye.signals import BaseSignal, Entry, IntSignal, create_signal

# ---------------------------------------------------------------------------
# read wpilog header bytes
# ---------------------------------------------------------------------------
valid_magic = MAGIC + struct.pack("<H", VERSION)
@pytest.mark.parametrize("buf, expected_offset", [
    (valid_magic + struct.pack("<I", 0), 12),
    (valid_magic + struct.pack("<I", 3) + b'foo', 15)
])
def test_parse_wpilog_header(buf: bytes, expected_offset: int) -> None:
    assert parse_wpilog_header(buf) == expected_offset

invalid_magic   = b'WPILEG' + struct.pack("<H", VERSION)
invalid_version = MAGIC     + struct.pack("<H", VERSION + 1)
@pytest.mark.parametrize("buf, match", [
    (valid_magic, "too short"),
    (invalid_magic   + struct.pack("<I", 0), "bad magic"),
    (invalid_version + struct.pack("<I", 0), "unsupported version"),
    (valid_magic     + struct.pack("<I", 3), "too short"),
])
def test_parse_wpilog_header_raises(buf: bytes, match: str) -> None:
    with pytest.raises(LogFormatError, match=match):
        parse_wpilog_header(buf)

# ---------------------------------------------------------------------------
# record header helpers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bitfield, expected", [
    (0b1111_0000_0000, (1, 1, 1)),
    (0b1111_1111, (4, 4, 16)),
    (0b0000_0011, (4, 1, 1)),
    (0b0000_1100, (1, 4, 1)),
    (0b1111_0000, (1, 1, 16)),
    (0b1101_1001, (2, 3, 14)),
])
def test_decode_header_bitfield(bitfield: int, expected: tuple[int, int, int]) -> None:
    '''
    affirmatively test header bitfield edge cases and real data
    '''
    assert decode_header_bitfield(bitfield) == expected


@pytest.mark.parametrize("buf, expected", [
    (bytes.fromhex('0000000000') , (0,     0,   0, 5)),
    (bytes.fromhex('0000FFFFFF') , (255, 255, 255, 5)),
    (bytes.fromhex('0000FF0000') , (255,   0,   0, 5)),
    (bytes.fromhex('000000FF00') , (0,   255,   0, 5)),
    (bytes.fromhex('00000000FF') , (0,     0, 255, 5)),
    (bytes.fromhex('0015000000000000') , (0,         0,     0, 8)),
    (bytes.fromhex('0015FFFFFFFFFFFF') , (65535, 65535, 65535, 8)),
    (bytes.fromhex('0015FFFF00000000') , (65535,     0,     0, 8)),
    (bytes.fromhex('00150000FFFF0000') , (0,     65535,     0, 8)),
    (bytes.fromhex('001500000000FFFF') , (0,         0, 65535, 8)),
    # timestamp: 1a1d4d LE = 0x4d1d1a = 5053722
    (bytes.fromhex('0020001e1a1d4d') , (0, 30, 5053722, 7)),
])
def test_read_record_header_with_offset(buf: bytes, expected: tuple[int, int, int, int]) -> None:
    '''
    affirmatively test record header edge cases and real data
    '''
    assert read_record_header(buf, 1) == expected

def test_read_record_header_raises_past_end() -> None:
    '''
    negatively test record header raises value error if buffer is too short
    '''
    buf = bytes.fromhex('0020001e1a1d')
    with pytest.raises(LogFormatError):
        read_record_header(buf, 1)

# ---------------------------------------------------------------------------
# control record decoding helpers
# ---------------------------------------------------------------------------
#   offset   entry id   name len   name             type len   type           metadata len  metadata
one  = '11   02000000   07000000   636f6e736f6c65   06000000   737472696e67   00000000'
mt   = '11   09000000   00000000                    00000000                  00000000'
meta = '11   04000000   03000000   616263           05000000   696e743634     02000000      7b7d'
@pytest.mark.parametrize("buf, expected", [
    (bytes.fromhex(one),  (Entry(2,"console", "string",   ""), 30)),
    (bytes.fromhex(mt),   (Entry(9,       "",       "",   ""), 17)),
    (bytes.fromhex(meta), (Entry(4,    "abc",  "int64", "{}"), 27)),
])
def test_read_start_record_with_offset(buf: bytes, expected: tuple[Entry, int]) -> None:
    '''
    affirmatively test read start record reads control record
    '''
    assert read_start_record(buf, 1) == expected

def test_read_start_record_raises_on_truncated() -> None:
    '''
    negative test record header raises value error if header is malformed
    '''
    truncated = '11 02000000 07000000 636f6e'
    with pytest.raises(LogFormatError):
        read_start_record(bytes.fromhex(truncated), 1)

def test_read_finish_record() -> None:
    '''
    affirmatively test read finish record reads a 4-byte uint
    '''
    buf = bytes.fromhex("00 2a000000")
    assert read_finish_record(buf, 1) == (42, 5)

def test_read_metadata_record() -> None:
    # entry_id=7 (4 bytes), then a length-prefixed metadata string "{}"
    # 07000000            entry_id = 7
    # 02000000 7b7d       metadata: len=2, "{}"
    buf = bytes.fromhex("00 07000000 02000000 7b7d")   # leading 00 skipped
    assert update_metadata_record(buf, 1) == (7, "{}", 11)

# ---------------------------------------------------------------------------
# data record decoding helpers
# ---------------------------------------------------------------------------

#      offset   type  entry id   name len   name             type len   type           metadata len  metadata #noqa: E501
start   = '11   00    02000000   07000000   636f6e736f6c65   06000000   737472696e67   03000000     666F6F' #noqa: E501
#      offset   type  entry id   metadata len  metadata
update  = '11   02    02000000   03000000      666F6F'
#      offset   type  entry id
finish  = '11   01    02000000'
@pytest.mark.parametrize("init_entries, bytestr, offset, expected_entries", [
    ({},                                      start,  1, {2: Entry(2, "console", "string", "foo")}),
    ({2: Entry(2, "console", "string", "")}, update,  1, {2: Entry(2, "console", "string", "foo")}),
    ({2: Entry(2, "console", "string", "")}, finish,  1, {2: Entry(2, "console", "string", "")}),
])
def test_apply_control_record(init_entries: dict[int, Entry],
                              bytestr: str,
                              offset: int,
                              expected_entries: dict[int, Entry]) -> None:
    buf = bytes.fromhex(bytestr)
    assert apply_control_record(buf, offset, init_entries) == len(buf)
    assert init_entries == expected_entries

#       offset   type  entry id   name len   name             type len   type           metadata len  metadata #noqa: E501
start    = '11   00    02000000   07000000   636f6e736f6c65   06000000   737472696e67   03000000     666F6F' #noqa: E501
#       offset   type  entry id   metadata len  metadata
update   = '11   02    03000000   03000000      666F6F'
#       offset   type  entry id   metadata len  metadata
invalid  = '11   03    02000000   03000000      666F6F'
@pytest.mark.parametrize("init_entries, bytestr, offset", [
    ({2: Entry(2, "console", "string", "foo")},   start,  1),
    ({2: Entry(2, "console", "string", "")},     update,  1),
    ({2: Entry(2, "console", "string", "")},    invalid,  1),
])
def test_apply_control_record_raises(init_entries: dict[int, Entry],
                                     bytestr: str,
                                     offset: int,) -> None:
    buf = bytes.fromhex(bytestr)
    with pytest.raises(LogFormatError):
        apply_control_record(buf, offset, init_entries)

# ---------------------------------------------------------------------------
# record decoding helpers
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("buf, offset, size, expected", [
    (b"", 0, 0, (b"", 0)),
    (b"a", 0, 1, (b"a", 1)),
    (b"abc", 1, 2, (b"bc", 3)),
    (b"abcd", 1, 2, (b"bc", 3)),
])
def test_read_record(buf: bytes, offset: int, size: int, expected: tuple[bytes, int]) -> None:
    assert read_record(buf, offset, size) == expected

@pytest.mark.parametrize("buf, offset, size", [
    (b"", 0, 1),
    (b"a", 0, 2),
    (b"a", 1, 1),
])
def test_read_record_raises(buf: bytes, offset: int, size: int) -> None:
    match_str = f"{size} bytes at offset {offset} but only {len(buf) - offset} remain"
    with pytest.raises(LogFormatError, match=match_str):
        read_record(buf, offset, size)
# ---------------------------------------------------------------------------
# log parser class
# ---------------------------------------------------------------------------

def test_init(tmp_path: Path) -> None:
    valid_header = MAGIC + struct.pack("<H", VERSION) + struct.pack("<I", 0)
    path = tmp_path / "test.wpilog"
    path.write_bytes(valid_header)
    parser = LogParser.from_file(path)
    assert parser._record_start == 12

def test_init_raises_on_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        LogParser.from_file(tmp_path / "nonexistent.wpilog")

def test_init_raises_on_malformed_log(tmp_path: Path) -> None:
    path = tmp_path / "test.wpilog"
    path.write_bytes(MAGIC)
    with pytest.raises(LogFormatError, match=re.escape(str(path))):
        LogParser.from_file(path)

def test_apply_data_record_creates_signal() -> None:
    payload = struct.pack("<q", 12000)
    signals: dict[str, BaseSignal[Any]] = {}
    entry = Entry(1, "voltage", "int64", "")
    apply_data_record(entry, 1000, payload, signals)

    assert "voltage" in signals
    assert isinstance(signals["voltage"], IntSignal)
    assert signals["voltage"].timestamps == [1000]

def test_apply_data_record_reuses_existing_signal() -> None:
    payload = struct.pack("<q", 12000)
    existing = create_signal(Entry(1, "voltage", "int64", ""))
    existing.append_payload(500, payload)
    signals = {"voltage": existing}

    apply_data_record(Entry(1, "voltage", "int64", ""), 1000, payload, signals)

    assert signals["voltage"] is existing
    assert existing.timestamps == [500, 1000]
