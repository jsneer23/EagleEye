import pytest

from eagleeye.parsers.wpilog_parser import decode_header_bitfield, read_record_header


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
def test_read_record_header(buf: bytes, expected: tuple[int, int, int, int]) -> None:
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
