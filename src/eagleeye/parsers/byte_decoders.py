import struct


# ---------------------------------------------------------------------------
# byte decoder bounds check
# ---------------------------------------------------------------------------
def _check_bounds(offset: int, read_width: int, length: int) -> None:
    '''
    raise ValueError if reading `read_width` bytes at `offset` runs past the buffer end
    '''
    if offset + read_width > length:
        raise ValueError(
            f"read of {read_width} bytes at {offset} terminates past the end of the file "
            f" ({length}). log may be malformed/truncated."
        )

# ---------------------------------------------------------------------------
# byte decoders
# ---------------------------------------------------------------------------

def read_uint(buf: bytes, offset: int, read_width: int) -> tuple[int, int]:
    '''
    buffer reader. starts at `offset` and reads `read_width` bytes and returns the new offset
    as well as the value read in little endian
    '''
    if read_width <= 0:
        raise ValueError(f"buffer `read_width` must be positive, got {read_width}."
                         f"log may be malformed.")

    _check_bounds(offset, read_width, len(buf))

    end = offset + read_width
    value = int.from_bytes(buf[offset:end], "little")

    return value, end

def read_string(buf: bytes, offset: int) -> tuple[str, int]:
    '''
    string reader. used for the start of control record payloads where the length
    of the string to be read in appears in the buffer right before the string.
    '''
    read_width, offset = read_uint(buf, offset, 4)
    _check_bounds(offset, read_width, len(buf))
    end = offset + read_width

    try:
        text = buf[offset:end].decode("utf-8")
    except UnicodeDecodeError as e:
        raise ValueError(
            f"invalid utf-8 conversion for string of length {read_width} at offset {offset}."
            f"log may be malformed."
        ) from e

    return text, end

def u8(buf: bytes, offset: int) -> tuple[int, int]:
    '''read an unsigned 8-bit int on the buffer starting at the given offset'''
    _check_bounds(offset, 1, len(buf))
    return buf[offset], offset + 1

def i16(buf: bytes, offset: int) -> tuple[int, int]:
    '''read a 16-bit int on the buffer starting at the given offset'''
    _check_bounds(offset, 2, len(buf))
    return struct.unpack_from("<h", buf, offset)[0], offset + 2

def i32(buf: bytes, offset: int) -> tuple[int, int]:
    '''read a 32-bit int on the buffer starting at the given offset'''
    _check_bounds(offset, 4, len(buf))
    return struct.unpack_from("<i", buf, offset)[0], offset + 4

def i64(buf: bytes, offset: int) -> tuple[int, int]:
    '''read a 64-bit int on the buffer starting at the given offset'''
    _check_bounds(offset, 8, len(buf))
    return struct.unpack_from("<q", buf, offset)[0], offset + 8

def f32(buf: bytes, offset: int) -> tuple[float, int]:
    '''read a 32-bit float on the buffer starting at the given offset'''
    _check_bounds(offset, 4, len(buf))
    return struct.unpack_from("<f", buf, offset)[0], offset + 4

def f64(buf: bytes, offset: int) -> tuple[float, int]:
    '''read a 64-bit float on the buffer starting at the given offset'''
    _check_bounds(offset, 8, len(buf))
    return struct.unpack_from("<d", buf, offset)[0], offset + 8
