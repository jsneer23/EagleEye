from typing import Any

import pytest

from eagleeye.errors import PayloadError
from eagleeye.signals import (
    BaseSignal,
    ByteSignal,
    Entry,
    FloatArraySignal,
    FloatSignal,
    IntSignal,
    create_signal,
)


@pytest.mark.parametrize("type_str, sig_type", [
    ("int64", IntSignal),
    ("double", FloatSignal),
    ("float", FloatSignal),
    ("double[]", FloatArraySignal),
    ("float[]", FloatArraySignal),
])
def test_create_signal_type_dict(type_str: str, sig_type: type[BaseSignal[Any]]) -> None:
    entry = Entry(2, "name", type_str, "{meta: data}")
    sig = create_signal(entry)
    assert isinstance(sig, sig_type)
    assert sig.name == "name" and sig.type == type_str

@pytest.mark.parametrize("type_str", [
    "json",
    "proto:SomeMessage",       # startswith "proto:"
    "struct:MyStruct",         # startswith "struct:"
    "photonstruct:Foo",        # startswith "photonstruct:"
    "MyThingschema",           # endswith "schema"
])
def test_create_signal_returns_bytesignal_for_raw_types(type_str: str) -> None:
    entry = Entry(1, "x", type_str, "")
    sig = create_signal(entry)
    assert isinstance(sig, ByteSignal)
    assert sig.name == "x" and sig.type == type_str

def test_create_signal_raises_on_unknown_type() -> None:
    entry = Entry(1, "x", "totally_unknown_type", "")
    with pytest.raises(PayloadError, match="unknown entry type"):
        create_signal(entry)
