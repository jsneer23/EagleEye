import pytest

from eagleeye.parsers.signals import Entry
from eagleeye.parsers.wpilog_parser import (
    apply_control_record,
    decode_header_bitfield,
    read_finish_record,
    read_metadata_record,
    read_record_header,
    read_start_record,
)


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
    with pytest.raises(ValueError):
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
    with pytest.raises(ValueError):
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
    assert read_metadata_record(buf, 1) == (7, "{}", 11)

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
    with pytest.raises(ValueError):
        apply_control_record(buf, offset, init_entries)

# ---------------------------------------------------------------------------
# log parser class
# ---------------------------------------------------------------------------