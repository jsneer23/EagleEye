import struct

from eagleeye.parsers.wpilog_parser import MAGIC, VERSION


# ---------------------------------------------------------------------------
# private helpers
# ---------------------------------------------------------------------------
def _min_width(value: int, max_width: int = 4) -> int:
    '''
    given an integer 'value', return minimum number of bytes needed to store it

    throws ValueError if minumum > supplied 'max_width' (default 4)
    '''
    width = max(1, (value.bit_length() + 7) // 8)
    if width > max_width:
        raise ValueError(f"{value} needs {width} bytes (max {max_width})")
    return width

def _lstr(s: str) -> bytes:
    '''
    return string as bytes with str length prepended
    '''
    raw = s.encode()
    return struct.pack("<I", len(raw)) + raw

# ---------------------------------------------------------------------------
# control record payloads
# ---------------------------------------------------------------------------

def start(entry_id: int, name: str, type_: str, metadata: str = "") -> bytes:
    return b"\x00" + struct.pack("<I", entry_id) + _lstr(name) + _lstr(type_) + _lstr(metadata)


def finish(entry_id: int) -> bytes:
    return b"\x01" + struct.pack("<I", entry_id)


def update(entry_id: int, metadata: str) -> bytes:
    return b"\x02" + struct.pack("<I", entry_id) + _lstr(metadata)

# ---------------------------------------------------------------------------
# record framing
# ---------------------------------------------------------------------------

def record(
    entry_id: int,
    timestamp: int,
    payload: bytes,
) -> bytes:
    '''
    wrap a payload in a record header. widths default to the minimum that fits.
    '''
    id_width = _min_width(entry_id)
    size_width =  _min_width(len(payload))
    ts_width = _min_width(timestamp, max_width = 6)

    bitfield = (id_width - 1) | ((size_width - 1) << 2) | ((ts_width - 1) << 4)

    return (
        bytes([bitfield])
        + entry_id.to_bytes(id_width, "little")
        + len(payload).to_bytes(size_width, "little")
        + timestamp.to_bytes(ts_width, "little")
        + payload
    )

def control(payload: bytes, timestamp: int = 0) -> bytes:
    '''
    control record is just a record with entry_id 0
    '''
    return record(0, timestamp, payload)

def log(*records: bytes, extra_header: bytes = b"") -> bytes:
    return (
        MAGIC
        + struct.pack("<H", VERSION)
        + struct.pack("<I", len(extra_header))
        + extra_header
        + b"".join(records)
    )
