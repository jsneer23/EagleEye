import struct
from collections.abc import Callable

import pytest

from eagleeye.parsers.byte_decoders import f32, f64, i16, i32, i64, read_string, read_uint, u8


def test_read_uint() -> None:
    '''
    affirmatively test read_unit reads the buffer at non_zero offset
    '''
    buf = b'zabcd'
    # bytes at offset 1, width 3, are b'abc' = 0x61, 0x62, 0x63
    # little-endian: 0x61 + 0x62*256 + 0x63*65536 = 6513249
    print(0x61 + 0x62*256 + 0x63*65536)
    assert read_uint(buf, 1, 3) == (6513249, 4)

def test_func_reads_string_value_at_offset() -> None:
    '''
    affirmatively test read_string returns the 4-byte length string located at given non-zero offset
    '''
    buf = struct.pack("<I", 3) + b"foo" + struct.pack("<I", 3) + b"bar"
    assert read_string(buf, 7) == ("bar", len(buf))

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
    affirmatively test reading past the buffer end raises ValueError (malformed logfile)
    '''
    with pytest.raises(ValueError):
        f(bytes([]), 0)

def test_uint_raises_past_end() -> None:
    '''
    affirmatively test reading past the buffer end raises ValueError (malformed logfile)
    '''
    with pytest.raises(ValueError):
        read_uint(bytes([]), 0, 4)
