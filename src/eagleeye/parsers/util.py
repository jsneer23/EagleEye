import struct
from abc import ABC, abstractmethod
from bisect import bisect_left, bisect_right
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import ClassVar


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

# ---------------------------------------------------------------------------
# abstract and base payload dataclasses
# ---------------------------------------------------------------------------

@dataclass(kw_only=True)
class BaseSignal[V](ABC):
    name: str
    type: str
    timestamps: list[int] = field(default_factory=list)
    values: list[V] = field(default_factory=list)

    @abstractmethod
    def append_payload(self, timestamp: int, payload: bytes) -> None:
        ...

    def zip_between_ts(self,
                       lo_ts: int | None = None,
                       hi_ts: int | None = None) -> Iterator[tuple[int, V]]:

        if lo_ts is None or hi_ts is None:
            return iter([])

        i = bisect_left(self.timestamps, lo_ts)
        j = bisect_right(self.timestamps, hi_ts)

        return zip(self.timestamps[i:j], self.values[i:j], strict=True)

@dataclass(kw_only=True)
class StructSignal[V](BaseSignal[V]):

    _fmt: str = field(init=False)
    _FORMATS: ClassVar[dict[str, str]]  = {
        "int16": "<h",
        "int32": "<i",
        "int64": "<q",
        "boolean": "<?",
        "double": "<d",
        "float": "<f",
        "int16[]": "<h",
        "int32[]": "<i",
        "int64[]": "<q",
        "boolean[]": "<?",
        "double[]": "<d",
        "float[]": "<f",
    }

    def __post_init__(self) -> None:
        self._fmt = self._FORMATS[self.type]

    def append_payload(self, timestamp: int, payload: bytes) -> None:
        self.timestamps.append(timestamp)
        self.values.append(struct.unpack_from(self._fmt, payload, 0)[0])

@dataclass(kw_only=True)
class StructArraySignal[V](StructSignal[list[V]]):

    def append_payload(self, timestamp: int, payload: bytes) -> None:
        self.timestamps.append(timestamp)
        self.values.append([v for (v,) in struct.iter_unpack(self._fmt, payload)])

@dataclass(kw_only=True)
class IntSignal(StructSignal[int]):
    """int scalar signal."""
@dataclass(kw_only=True)
class FloatSignal(StructSignal[float]):
   """float scalar signal."""
@dataclass(kw_only=True)
class BoolSignal(StructSignal[bool]):
    """bool scalar signal."""
@dataclass(kw_only=True)
class IntArraySignal(StructArraySignal[int]):
    """list[int] scalar signal."""
@dataclass(kw_only=True)
class FloatArraySignal(StructArraySignal[float]):
    """list[float] scalar signal."""
@dataclass(kw_only=True)
class BoolArraySignal(StructArraySignal[bool]):
    """list[bool] scalar signal."""

@dataclass(kw_only=True)
class StrSignal(BaseSignal[str]):

    def append_payload(self, timestamp: int, payload: bytes) -> None:
        self.timestamps.append(timestamp)
        self.values.append(payload.decode("utf-8"))

@dataclass(kw_only=True)
class StrArraySignal(BaseSignal[list[str]]):

    def append_payload(self, timestamp: int, payload: bytes) -> None:
        self.timestamps.append(timestamp)
        array_length, offset = read_uint(payload, 0, 4)
        items: list[str] = []
        for _ in range(array_length):
            string, offset = read_string(payload, offset)
            items.append(string)
        self.values.append(items)

@dataclass(kw_only=True)
class ByteSignal(BaseSignal[bytes]):

    def append_payload(self, timestamp: int, payload: bytes) -> None:
        self.timestamps.append(timestamp)
        self.values.append(payload)
