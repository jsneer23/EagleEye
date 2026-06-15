import struct
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# byte reader helpers
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

# ---------------------------------------------------------------------------
# record header helpers
# ---------------------------------------------------------------------------

def decode_header_bitfield(bitfield: int) -> tuple[int, int, int]:
    '''
    decode header bitfield. see parser/README.md for breakdown
    '''
    entry_id_len = (bitfield & 0b0000_0011) + 1
    payload_size_len = ((bitfield & 0b0000_1100) >> 2) + 1 # notice bitshift after mask
    timestamp_len = ((bitfield & 0b1111_0000) >> 4) + 1

    return entry_id_len, payload_size_len, timestamp_len

def read_record_header(buf: bytes, offset: int) -> tuple[int, int, int, int]:
    '''
    read payload header. see parser/README.md for breakdown
    '''
    # read and decode variable header bitfield
    bitfield, offset = read_uint(buf, offset, 1)
    entry_id_len, payload_size_len, timestamp_len = decode_header_bitfield(bitfield)

    # read entry, size, and timestamp header bytes
    entry_id, offset = read_uint(buf, offset, entry_id_len)
    payload_size, offset = read_uint(buf, offset, payload_size_len)
    timestamp, offset = read_uint(buf, offset, timestamp_len)

    return entry_id, payload_size, timestamp, offset

# ---------------------------------------------------------------------------
# payload dataclasses
# ---------------------------------------------------------------------------

# return type alias because payloads can return many different types
type Payload = float | int | bool | str | bytes | list[float] | list[int] | list[bool] | list[str]

@dataclass
class Entry:
    entry_id: int
    name: str
    type: str
    metadata: str

@dataclass
class Signal:
    name: str
    type: str
    timestamps: list[int]
    values: list[Payload]

# ---------------------------------------------------------------------------
# control record decoding helpers
# ---------------------------------------------------------------------------

def read_start_record(buf: bytes, offset: int) -> tuple[Entry, int]:

    entry_id, offset = read_uint(buf, offset, 4)
    name,     offset = read_string(buf, offset)
    type_,    offset = read_string(buf, offset)
    metadata, offset = read_string(buf, offset)

    return Entry(entry_id, name, type_, metadata), offset

def read_finish_record(buf: bytes, offset: int) -> tuple[int, int]:

    entry_id, offset = read_uint(buf, offset, 4)

    return entry_id, offset

def read_metadata_record(buf: bytes, offset: int) -> tuple[int, str, int]:

    entry_id, offset = read_uint(buf, offset, 4)
    metadata, offset = read_string(buf, offset)

    return entry_id, metadata, offset

def apply_control_record(buf: bytes, offset: int, entries: dict[int, Entry]) -> int:

    control_type, offset = read_uint(buf, offset, 1)

    if control_type == 0:
        entry, offset = read_start_record(buf, offset)
        entries[entry.entry_id] = entry

    elif control_type == 1:
        _entry_id, offset = read_finish_record(buf, offset)
        # in case logs appear out of order don't pop - entries.pop(entry_id, None)
        # _entry_id deliberately unused for now

    elif control_type == 2:
        entry_id, metadata, offset = read_metadata_record(buf, offset)
        if entry_id in entries:
            entries[entry_id].metadata = metadata
        else:
            raise ValueError(
                f"Unknown entry_id {entry_id} for updating metadata at offset"
                f" {offset}. Log may be corrupted."
            )

    else:
        raise ValueError(f"Unknown control type {control_type} at offset {offset}")

    return offset

# ---------------------------------------------------------------------------
# record payload parser
# ---------------------------------------------------------------------------


def decode_payload(entry: Entry, payload: bytes) -> Payload:
    '''
    decode payloads based on payload type defined by control record
    '''

    t = entry.type

    if t == "int64":
        return struct.unpack_from("<q", payload, 0)[0]
    elif t == "boolean":
        return struct.unpack_from("<?", payload, 0)[0]
    elif t == "double":
        return struct.unpack_from("<d", payload, 0)[0]
    elif t == "float":
        return struct.unpack_from("<f", payload, 0)[0]
    elif t == "string":
        return payload.decode("utf-8")
    elif t == "int64[]":
        return [v for (v,) in struct.iter_unpack("<q", payload)]
    elif t == "boolean[]":
        return [v for (v,) in struct.iter_unpack("<?", payload)]
    elif t == "double[]":
        return [v for (v,) in struct.iter_unpack("<d", payload)]
    elif t == "float[]":
        return [v for (v,) in struct.iter_unpack("<f", payload)]
    elif t == "string[]":
        array_length, offset = read_uint(payload, 0, 4)
        items: list[str] = []
        for _ in range(array_length):
            string, offset = read_string(payload, offset)
            items.append(string)
        return items
    elif t == "json":
        return payload.decode("utf-8")
    elif t.startswith(("proto:", "struct:", "photonstruct:")) or t.endswith("schema"):
        #TODO: implement parsing of some of these structs, maybe
        return payload
    else:
        raise ValueError(f"Unhandled type {t!r} for entry {entry.name!r}")


# ---------------------------------------------------------------------------
# log parser class
# ---------------------------------------------------------------------------

class LogParser:

    MAGIC = b"WPILOG"
    VERSION = 0x0100
    FORMAT = "<H"

    def __init__(self, file_path: str | Path) -> None:
        self._path = Path(file_path)

        try:
            with open(self._path, "rb") as fh:
                self._buf = fh.read()
        except OSError as e:
            raise ValueError(f"could not read {self._path}: {e}") from e

        self._record_start = self._parse_header()

    def _parse_header(self) -> int:
        '''
        validaton function for testing that the file is actually a wpilog file.
        it will check that the first bytes are "WPILOG" and that the version is
        currently supported.
        '''

        buf = self._buf

        if len(buf) < 12:
            raise ValueError(f"{self._path}: file too short. ({len(buf)} bytes)")
        if buf[:6] != self.MAGIC:
            raise ValueError(f"{self._path}: bad magic {buf[:6]!r}, expected {self.MAGIC!r}")
        version, offset = read_uint(buf, 6, 2)
        if version != self.VERSION:
            raise ValueError(f"{self._path}: unsupported version {version:#06x}")

        extra_len, offset = read_uint(buf, offset, 4)
        return offset + extra_len

    def parse_data(self) -> dict[int, Signal]:

        buf = self._buf
        offset = self._record_start

        entries: dict[int, Entry] = {}
        signals: dict[int, Signal] = {}

        while offset < len(buf):

            entry_id, payload_size, timestamp, offset = read_record_header(buf, offset)
            payload = buf[offset:offset+payload_size]
            offset += payload_size

            if entry_id == 0:
                apply_control_record(payload, 0, entries)
            else:
                entry = entries.get(entry_id)

                if entry is None:
                    raise ValueError(f"Unknown entry id {entry_id} at offset {offset}")

                value = decode_payload(entry, payload)
                sig = signals.get(entry_id)

                if sig is None:
                    sig = Signal(entry.name, entry.type, [], [])
                    signals[entry_id] = sig

                sig.timestamps.append(timestamp)
                sig.values.append(value)

        if offset != len(buf):
            raise ValueError(f"trailing bytes or truncation: stopped at {offset} of {len(buf)}")

        return signals


if __name__ == "__main__":
    '''
    main function for testing this class piecemeal
    '''
    import sys

    parser = LogParser(sys.argv[1])
    signals = parser.parse_data()

    print(f"valid: {parser._path}  ({len(parser._buf):,} bytes)")

    for signal in signals.values():
        print(signal.name)
