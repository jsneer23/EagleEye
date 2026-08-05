import struct
from abc import ABC, abstractmethod
from bisect import bisect_left, bisect_right
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, ClassVar

from eagleeye.byte_decoders import read_string, read_uint
from eagleeye.errors import PayloadError, safe

# ---------------------------------------------------------------------------
# abstract and base payload dataclasses
# ---------------------------------------------------------------------------

@dataclass(kw_only=True)
class BaseSignal[V](ABC):
    name: str
    type: str
    timestamps: list[int] = field(default_factory=list[int])
    values: list[V] = field(default_factory=list[V])

    def append_payload(self, timestamp: int, payload: bytes) -> None:
        """decode and append payload. raises PayloadError on malformed input."""
        try:
            decoded = self._decode_payload(payload)
        except (struct.error, UnicodeDecodeError) as e:
            raise PayloadError(f"invalid payload for {safe(self.name)} ({safe(self.type)})") from e

        self.timestamps.append(timestamp)
        self.values.append(decoded)

    @abstractmethod
    def _decode_payload(self, payload: bytes) -> V:
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
class PrimitiveSignal[V](BaseSignal[V]):

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

    def _decode_payload(self, payload: bytes) -> V:
        return struct.unpack_from(self._fmt, payload, 0)[0]

@dataclass(kw_only=True)
class PrimitiveArraySignal[T](PrimitiveSignal[list[T]]):

    def _decode_payload(self, payload: bytes) -> list[T]:
        return [v for (v,) in struct.iter_unpack(self._fmt, payload)]

@dataclass(kw_only=True)
class IntSignal(PrimitiveSignal[int]):
    """int scalar signal."""
@dataclass(kw_only=True)
class FloatSignal(PrimitiveSignal[float]):
   """float scalar signal."""
@dataclass(kw_only=True)
class BoolSignal(PrimitiveSignal[bool]):
    """bool scalar signal."""
@dataclass(kw_only=True)
class IntArraySignal(PrimitiveArraySignal[int]):
    """list[int] scalar signal."""
@dataclass(kw_only=True)
class FloatArraySignal(PrimitiveArraySignal[float]):
    """list[float] scalar signal."""
@dataclass(kw_only=True)
class BoolArraySignal(PrimitiveArraySignal[bool]):
    """list[bool] scalar signal."""

@dataclass(kw_only=True)
class StrSignal(BaseSignal[str]):

    def _decode_payload(self, payload: bytes) -> str:
        return payload.decode("utf-8")

@dataclass(kw_only=True)
class StrArraySignal(BaseSignal[list[str]]):

    def _decode_payload(self, payload: bytes) -> list[str]:
        array_length, offset = read_uint(payload, 0, 4)
        items: list[str] = []
        for _ in range(array_length):
            string, offset = read_string(payload, offset)
            items.append(string)
        return items

@dataclass(kw_only=True)
class ByteSignal(BaseSignal[bytes]):

    def _decode_payload(self, payload: bytes) -> bytes:
        return payload

# ---------------------------------------------------------------------------
# decoding payload dataclass
# ---------------------------------------------------------------------------

@dataclass
class Entry:
    entry_id: int
    name: str
    type: str
    metadata: str

# ---------------------------------------------------------------------------
# signal creation
# ---------------------------------------------------------------------------

_SIGNAL_TYPES: dict[str, type[BaseSignal[Any]]] = {
    "int64":     IntSignal,
    "boolean":   BoolSignal,
    "double":    FloatSignal,
    "float":     FloatSignal,
    "string":    StrSignal,
    "int64[]":   IntArraySignal,
    "boolean[]": BoolArraySignal,
    "double[]":  FloatArraySignal,
    "float[]":   FloatArraySignal,
    "string[]":  StrArraySignal,
}

def create_signal(entry: Entry) -> BaseSignal[Any]:

    if entry.type in _SIGNAL_TYPES:
        cls = _SIGNAL_TYPES[entry.type]
    elif (entry.type == "json" or
        entry.type.startswith(("proto:", "struct:", "photonstruct:")) or
        entry.type.endswith("schema")
    ):
        cls = ByteSignal
    else:
        raise PayloadError(f"unknown entry type {safe(entry.type)}"
                           f" for entry {safe(entry.name)}")

    return cls(name=entry.name, type=entry.type)
