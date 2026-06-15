import struct
from pathlib import Path

# ---------------------------------------------------------------------------
# byte reader and header helper functions
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

def decode_header_bitfield(bitfield: int) -> tuple[int, int, int]:
    '''
    decode header bitfield. see parser/README.md for breakdown
    '''
    entry_id_len = (bitfield & 0b0000_0011) + 1
    payload_size_len = (bitfield & 0b0000_1100) + 1
    timestamp_len = (bitfield & 0b1111_0000) + 1

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

        self._validate()

    def _validate(self) -> bool:
        '''
        validaton function for testing that the file is actually a wpilog file.
        it will check that the first bytes are "WPILOG" and that the version is
        currently supported.
        '''
        if len(self._buf) < 12:
            raise ValueError(f"{self._path}: file too short. ({len(self._buf)} bytes)")
        if self._buf[:6] != self.MAGIC:
            raise ValueError(f"{self._path}: bad magic {self._buf[:6]!r}, expected {self.MAGIC!r}")
        version = struct.unpack_from("<H", self._buf, 6)[0]
        if version != self.VERSION:
            raise ValueError(f"{self._path}: unsupported version {version:#06x}")


if __name__ == "__main__":
    '''
    main function for testing this class piecemeal
    '''
    import sys

    parser = LogParser(sys.argv[1])
    print(f"valid: {parser._path}  ({len(parser._buf):,} bytes)")
