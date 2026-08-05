import struct
from collections.abc import Callable

import pytest

from eagleeye.byte_decoders import f32, f64, i16, i32, i64, read_string, read_uint, u8
from eagleeye.errors import LogFormatError


@pytest.mark.parametrize("buf, offset, read_width, result", [
    # bytes at offset 1, width 3, are b'abc' = 0x61, 0x62, 0x63
    # little-endian: 0x61 + 0x62*256 + 0x63*65536 = 6513249
    (b'zabcd', 1, 3, (6513249, 4)),
    (b'abcd', 0, 3, (6513249, 3)),
    (b'\x01\x00', 0, 2, (1, 2)),
    (b'\xff', 0, 1, (255, 1)),
    (b'\x00\x00\x00\x00', 0, 4, (0, 4)),
    (b'\xff\xff\xff\xff', 0, 4, (4294967295, 4)),
])
def test_read_uint(buf: bytes, offset: int, read_width: int, result: tuple[str, int]) -> None:
    '''
    affirmatively test read_unit reads the buffer at offset
    '''
    assert read_uint(buf, offset, read_width) == result

@pytest.mark.parametrize("buf, offset, read_width", [
    (b'', 0, 3),
    (b'', 1, 1),
    (b'abc', 0, 4),
    (b'abc', 0, 0),
    (b'abc', 0, -1),
])
def test_uint_raises_past_end(buf: bytes, offset: int, read_width: int) -> None:
    '''
    negatively test read_uint raises LogFormatError (malformed logfile)
    '''
    with pytest.raises(LogFormatError):
        read_uint(buf, offset, read_width)

@pytest.mark.parametrize("buf, offset, result", [
    (struct.pack("<I", 3) + b"foo" + struct.pack("<I", 3) + b"bar", 7, ("bar", 14)),
    (b"a" + struct.pack("<I", 0), 1, ("", 5)),
    (struct.pack("<I", 5) + "café".encode(), 0, ("café", 9)),
])
def test_func_read_string_value(buf: bytes, offset: int, result: tuple[str, int]) -> None:
    '''
    affirmatively test read_string reads the buffer at offset
    '''
    assert read_string(buf, offset) == result

def test_read_string_raises_on_truncated_text() -> None:
    '''
    negatively test reading past the buffer end raises LogFormatError (malformed logfile)
    '''
    buf = struct.pack("<I", 5) + b"ab"
    with pytest.raises(LogFormatError):
        read_string(buf, 0)

def test_read_string_raises_on_invalid_utf8() -> None:
    '''
    negatively test invalid utf-8 raises LogFormatError (malformed logfile)
    '''
    buf = struct.pack("<I", 2) + b"\xff\xfe"
    with pytest.raises(LogFormatError):
        read_string(buf, 0)

u8_buff =  [ 0x00, 0x2A, 0xFF]
i16_buff = [-0X8000, -5507, 0x7FFF]
i32_buff = [-0X80000000, -5507, 0x7FFFFFFF]
i64_buff = [-0X8000000000000000, -5507, 0x7FFFFFFFFFFFFFFF]
f32_buff = [0.0, -3.14159, 1e30]
f64_buff = [0.0, -2.718281828, 1e300]

test_data = [
        (u8,  bytes(u8_buff),                   u8_buff,  3*1),
        (i16, struct.pack("<hhh", *i16_buff),   i16_buff, 3*2),
        (i32, struct.pack("<iii", *i32_buff),   i32_buff, 3*4),
        (i64, struct.pack("<qqq", *i64_buff),   i64_buff, 3*8),
        (f32, struct.pack("<fff", *f32_buff),  [pytest.approx(v, rel=1e-6) for v in f32_buff], 3*4),
        (f64, struct.pack("<ddd", *f64_buff),  [pytest.approx(v) for v in f64_buff],           3*8)
    ]

@pytest.mark.parametrize(
    "f, raw_bytes, expected_values, distance",
    test_data
)
def test_func_reads_byte_value(f: Callable,
                               raw_bytes: bytes,
                               expected_values: list[int],
                               distance: int) -> None:
    '''
    affirmatively test each function returns the byte at a given non-zero offset
    '''
    offset = 0
    for expected in expected_values:
        value, offset = f(raw_bytes, offset)   # reuse the returned offset each time
        assert value == expected

    assert offset == distance

@pytest.mark.parametrize(
    "f",
    [u8, i16, i32, i64, f32, f64]
)
def test_f_raises_past_end(f: Callable) -> None:
    '''
    negatively test reading past the buffer end raises LogFormatError (malformed logfile)
    '''
    with pytest.raises(LogFormatError):
        f(bytes([]), 0)
