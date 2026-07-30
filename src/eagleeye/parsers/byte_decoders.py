import struct


# ---------------------------------------------------------------------------
# base byte decoder helpers
# ---------------------------------------------------------------------------
def read_uint(buf: bytes, offset: int, width: int) -> tuple[int, int]:
    '''
    buffer reader. starts at offset and reads width bytes and returns the new offset
    as well as the value read in little endian
    '''
    end = offset + width

    if end > len(buf):
        raise ValueError(
            f"read of {width} bytes at {offset} terminates past the end of the file "
            f" ({len(buf)})"
        )

    value = int.from_bytes(buf[offset:end], "little")
    return value, end

def read_string(buf: bytes, offset: int) -> tuple[str, int]:
    '''
    string reader. used for the start of control record payloads where the length
    of the string to be read in appears in the buffer right before the string.
    '''
    length, offset = read_uint(buf, offset, 4)
    end = offset + length
    text = buf[offset:end].decode("utf-8")

    return text, end

def u8(buffer: bytes, offset: int) -> tuple[int, int]:
    return buffer[offset], offset + 1

def i16(buffer: bytes, offset: int) -> tuple[int, int]:
    return struct.unpack_from("<i", buffer, offset)[0], offset + 2

def i32(buffer: bytes, offset: int) -> tuple[int, int]:
    return struct.unpack_from("<q", buffer, offset)[0], offset + 4

def i64(buffer: bytes, offset: int) -> tuple[int, int]:
    return struct.unpack_from("<q", buffer, offset)[0], offset + 8

def f32(buffer: bytes, offset: int) -> tuple[float, int]:
    return struct.unpack_from("<f", buffer, offset)[0], offset + 4

def f64(buffer: bytes, offset: int) -> tuple[float, int]:
    return struct.unpack_from("<d", buffer, offset)[0], offset + 8
