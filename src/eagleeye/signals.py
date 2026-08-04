import struct
from abc import ABC, abstractmethod
from bisect import bisect_left, bisect_right
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, ClassVar

from eagleeye.byte_decoders import read_string, read_uint

# ---------------------------------------------------------------------------
# abstract and base payload dataclasses
# ---------------------------------------------------------------------------

@dataclass(kw_only=True)
class BaseSignal[V](ABC):
    name: str
    type: str
    timestamps: list[int] = field(default_factory=list[int])
    values: list[V] = field(default_factory=list[V])

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
        raise ValueError(f"Unhandled type {entry.type!r} for entry {entry.name!r}")

    return cls(name=entry.name, type=entry.type)
