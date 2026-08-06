import unicodedata
from pathlib import Path
from typing import Any

from eagleeye.byte_decoders import read_string, read_uint
from eagleeye.errors import LogFormatError, safe
from eagleeye.signals import BaseSignal, Entry, create_signal

# ---------------------------------------------------------------------------
# sanitize inputs
# ---------------------------------------------------------------------------
_MAX_NAME = 256

def clean_name(raw: str) -> str:
    if len(raw) > _MAX_NAME:
        raise LogFormatError(f"entry name is {len(raw)} chars (max {_MAX_NAME})")

    name = unicodedata.normalize("NFC", raw)

    for ch in name:
        if unicodedata.category(ch) in {"Cc", "Cf", "Co", "Cs", "Cn"}:
            raise LogFormatError(f"entry name contains disallowed character U+{ord(ch):04X}")
    return name

_MAX_TYPE = 128

def check_type(raw: str) -> str:
    if len(raw) > _MAX_TYPE:
        raise LogFormatError(f"entry type is {len(raw)} chars (max {_MAX_TYPE})")
    if not raw.isascii() or not raw.isprintable():
        raise LogFormatError("entry type contains non-ASCII or control characters")
    return raw

# ---------------------------------------------------------------------------
# wpilog file constants
# ---------------------------------------------------------------------------

MAGIC = b"WPILOG"
VERSION = 0x0100

# ---------------------------------------------------------------------------
# read wpilog header bytes
# ---------------------------------------------------------------------------

def parse_wpilog_header(buf: bytes) -> int:
        '''
        validates the file is actually a wpilog file with correct magic and version
        and returns the buffer offset for the first data record
        '''
        min_header_len = 12

        if min_header_len > len(buf):
            raise LogFormatError(f"file too short. ({len(buf)} bytes)")
        if buf[:len(MAGIC)] != MAGIC:
            raise LogFormatError(f"bad magic {buf[:len(MAGIC)].hex()}, expected {MAGIC.hex()}")
        version, offset = read_uint(buf, len(MAGIC), 2)
        if version != VERSION:
            raise LogFormatError(f"unsupported version {version:#06x}")

        extra_len, offset = read_uint(buf, offset, 4)

        if offset + extra_len > len(buf):
            raise LogFormatError(f"file too short: header declares {extra_len} extra bytes at"
                                 f" offset {offset} but file is {len(buf)} bytes")

        return offset + extra_len

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
# control record decoding helpers
# ---------------------------------------------------------------------------

def read_start_record(buf: bytes, offset: int) -> tuple[Entry, int]:

    entry_id, offset = read_uint(buf, offset, 4)
    name,     offset = read_string(buf, offset)
    entry_type,    offset = read_string(buf, offset)
    metadata, offset = read_string(buf, offset)

    return Entry(entry_id, clean_name(name), check_type(entry_type), metadata), offset

def read_finish_record(buf: bytes, offset: int) -> tuple[int, int]:

    entry_id, offset = read_uint(buf, offset, 4)

    return entry_id, offset

def update_metadata_record(buf: bytes, offset: int) -> tuple[int, str, int]:

    entry_id, offset = read_uint(buf, offset, 4)
    metadata, offset = read_string(buf, offset)

    return entry_id, metadata, offset

def apply_control_record(buf: bytes, offset: int, entries: dict[int, Entry]) -> int:

    control_type, offset = read_uint(buf, offset, 1)

    if control_type == 0:
        entry, offset = read_start_record(buf, offset)
        if entry.entry_id in entries:
            existing = entries[entry.entry_id].name
            raise LogFormatError(f"start control record {safe(entry.name)} is attempting to"
                                 f" overwrite an existing log {safe(existing)} at entry_id"
                                 f" {entry.entry_id}. log may be malformed.")

        entries[entry.entry_id] = entry

    elif control_type == 1:
        _entry_id, offset = read_finish_record(buf, offset)
        # in case logs appear out of order don't pop - entries.pop(entry_id, None)
        # _entry_id deliberately unused for now

    elif control_type == 2:
        entry_id, metadata, offset = update_metadata_record(buf, offset)
        if entry_id in entries:
            entries[entry_id].metadata = metadata
        else:
            raise LogFormatError(f"Unknown entry_id {entry_id} for updating metadata at offset"
                                 f" {offset}. Log may be corrupted.")

    else:
        raise LogFormatError(f"Unknown control type {control_type} at offset {offset}")

    return offset

# ---------------------------------------------------------------------------
# data record decoding helpers
# ---------------------------------------------------------------------------

def apply_data_record(entry: Entry,
                      timestamp: int,
                      payload: bytes,
                      signals: dict[str, BaseSignal[Any]]) -> None:

    sig = signals.get(entry.name)

    if sig is None:
        sig = create_signal(entry)
        signals[entry.name] = sig

    sig.append_payload(timestamp, payload)

# ---------------------------------------------------------------------------
# record decoding helpers
# ---------------------------------------------------------------------------

def read_record(buf: bytes, offset: int, size: int) -> tuple[bytes, int]:

    if size < 0:
        raise LogFormatError(f"record declares negative size {size} of offset {offset}")

    end = offset + size

    if end > len(buf):
        raise LogFormatError(
            f"record declares {size} bytes at offset {offset} "
            f"but only {len(buf) - offset} remain"
        )
    return buf[offset:end], end

# ---------------------------------------------------------------------------
# log parser class
# ---------------------------------------------------------------------------

class LogParser:

    def __init__(self, buf: bytes, source: str = "<memory>") -> None:

        self._buf = buf

        try:
            self._record_start = parse_wpilog_header(buf)
        except LogFormatError as e:
            raise LogFormatError(f"{source}: {e}") from e

    @classmethod
    def from_file(cls, file_path: str | Path) -> "LogParser":

        path = Path(file_path)

        try:
            with open(path, "rb") as fh:
                buf = fh.read()
        except OSError as e:
            raise FileNotFoundError(f"could not read {path}: {e}") from e

        return cls(buf, str(path))

    def parse_data(self) -> tuple[dict[str, BaseSignal[Any]], int]:

        buf = self._buf
        offset = self._record_start

        entries: dict[int, Entry] = {}
        signals: dict[str, BaseSignal[Any]] = {}
        log_end_timestamp: int = 0

        while offset < len(buf):

            entry_id, record_size, timestamp, offset = read_record_header(buf, offset)
            record, offset = read_record(buf, offset, record_size)

            if entry_id == 0:
                apply_control_record(record, 0, entries)
            else:

                try:
                    entry = entries[entry_id]
                except KeyError:
                    e = LogFormatError(f"unknown entry_id {entry_id} at offset {offset}")
                    raise e from None

                apply_data_record(entry, timestamp, record, signals)
                log_end_timestamp = max(timestamp, log_end_timestamp)

        if offset != len(buf): # pragma: no cover - defensive invariant
            raise RuntimeError(f"parser error: parse completed at {offset} of {len(buf)} bytes")

        return signals, log_end_timestamp
