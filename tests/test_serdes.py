from __future__ import annotations

import dataclasses
import datetime
import decimal
import enum
import ipaddress
import json
import re
import typing
from types import MappingProxyType
from typing import ClassVar, Optional, Dict, TypeVar, Generic, List, Mapping

import orjson
import pytest
import ujson

import typic
import typic.api
import typic.common
import typic.ext.json
from tests import objects


@typic.klass
class FieldMapp:
    foo_bar: str = typic.field(default="bar", name="foo")


@typic.klass(serde=typic.flags(case=typic.common.Case.CAMEL))
class Camel:

    foo_bar: str = "bar"


@typic.klass(serde=typic.flags(signature_only=True))
class SigOnly:

    foo: ClassVar[str] = "foo"
    foo_bar: str = "bar"


@typic.klass(serde=typic.flags(omit=("bar",)))
class Omit:

    bar: str = "foo"
    foo: str = "bar"


@typic.klass
class ClassVarEnum:
    foo: ClassVar[objects.FooNum] = objects.FooNum.bar


class SubStr(str):
    ...


class SubURL(typic.URL):
    ...


@pytest.mark.parametrize(
    argnames=("obj", "expected"),
    argvalues=[
        (1, 1),
        (True, True),
        (1.0, 1.0),
        (None, None),
        (..., None),
        ("foo", "foo"),
        (b"foo", "foo"),
        (bytearray("foo", "utf-8"), "foo"),
        ({"foo"}, ["foo"]),
        (frozenset({"foo"}), ["foo"]),
        (("foo",), ["foo"]),
        (["foo"], ["foo"]),
        (MappingProxyType({"foo": 1}), {"foo": 1}),
        (typic.FrozenDict({"foo": 1}), {"foo": 1}),
        (ipaddress.IPv4Address("0.0.0.0"), "0.0.0.0"),
        (re.compile(r"foo"), "foo"),
        (datetime.datetime(1970, 1, 1), "1970-01-01T00:00:00"),
        (
            datetime.datetime(
                1970, 1, 1, tzinfo=datetime.timezone(datetime.timedelta(hours=1))
            ),
            "1970-01-01T00:00:00+01:00",
        ),
        (objects.Typic(var="foo"), {"var": "foo"}),
        (objects.Data(foo="foo"), {"foo": "foo"}),
        (objects.FromDict(), {"foo": None}),
        (decimal.Decimal("1000000000000000.3"), "1000000000000000.3"),
        (objects.FooNum.bar, "bar"),
        (objects.Class(var="foo"), {"var": "foo"}),
        (FieldMapp(), {"foo": "bar"}),
        (Camel(), {"fooBar": "bar"}),
        (SigOnly(), {"foo_bar": "bar"}),
        (Omit(), {"bar": "foo"}),
        (objects.FooNum.bar, objects.FooNum.bar.value),
        (
            {objects.FooNum.bar: objects.Forward(objects.FooNum.bar)},
            {"bar": {"foo": "bar"}},
        ),
        (typic.URL("foo"), "foo"),
        ([typic.URL("foo")], ["foo"]),
        (SubStr("foo"), "foo"),
        (SubURL("foo"), "foo"),
        (ClassVarEnum(), {"foo": objects.FooNum.bar.value}),
    ],
    ids=repr,
)
def test_primitive(obj, expected):
    primitive = typic.primitive(obj)
    assert primitive == expected
    assert isinstance(primitive, type(expected))


class MultiNum(enum.Enum):
    INT = 1
    STR = "str"


_KT = TypeVar("_KT")
_VT = TypeVar("_VT")


class GenDict(Generic[_KT, _VT], Dict):
    __serde_flags__ = typic.flags(fields=("foo_bar",), case=typic.common.Case.CAMEL)


class SerDict(Dict):
    __serde_flags__ = typic.flags(fields=("foo_bar",), case=typic.common.Case.CAMEL)


class CaseDict(Dict):
    __serde_flags__ = typic.flags(case=typic.common.Case.CAMEL)


@dataclasses.dataclass
class ListUnion:
    members: list[MemberInt | MemberStr]


@dataclasses.dataclass
class MemberStr:
    field: str


@dataclasses.dataclass
class MemberInt:
    field: int


@pytest.mark.parametrize(
    argnames=("t", "obj", "prim"),
    argvalues=[
        (Optional[str], None, None),
        (Optional[objects.Typic], None, None),
        (Optional[objects.Typic], objects.Typic(var="foo"), {"var": "foo"}),
        (MultiNum, MultiNum.INT, 1),
        (MultiNum, MultiNum.STR, "str"),
        (
            Dict[objects.FooNum, objects.Typic],
            {objects.FooNum.bar: objects.Typic(var="foo")},
            {"bar": {"var": "foo"}},
        ),
        (
            GenDict[str, int],
            GenDict(foo_bar=2),
            {"fooBar": 2},
        ),
        (
            SerDict,
            SerDict(foo_bar=2),
            {"fooBar": 2},
        ),
        (
            CaseDict,
            CaseDict(foo_bar=2),
            {"fooBar": 2},
        ),
        (objects.TDict, objects.TDict(a=1), {"a": 1}),
        (objects.NTup, objects.NTup(a=1), {"a": 1}),
        (
            ListUnion,
            ListUnion([MemberStr("string"), MemberInt(1)]),
            {"members": [{"field": "string"}, {"field": 1}]},
        ),
        (objects.SubTypic, objects.SubTypic(var="", sub=""), {"var": "", "sub": ""}),
        (Optional[objects.FooNum], None, None),
        (Optional[objects.FooNum], objects.FooNum.bar, objects.FooNum.bar.value),
    ],
)
def test_serde_serialize(t, obj, prim):
    r = typic.resolver.resolve(t)
    assert r.serialize(obj) == prim


@pytest.mark.parametrize(
    argnames=("t", "obj", "prim"),
    argvalues=[
        (Optional[str], None, None),
        (Optional[objects.Typic], None, None),
        (Optional[objects.Typic], objects.Typic(var="foo"), {"var": "foo"}),
        (MultiNum, MultiNum.INT, 1),
        (MultiNum, MultiNum.STR, "str"),
        (
            Dict[objects.FooNum, objects.Typic],
            {objects.FooNum.bar: objects.Typic(var="foo")},
            {"bar": {"var": "foo"}},
        ),
        (
            Dict[str, objects.Typical],
            {"key": objects.Typical(bar="bar", id=1)},
            {"key": {"bar": "bar", "id": 1}},
        ),
        (
            Dict[str, objects.Typical],
            {"key": objects.Typical(bar="bar")},
            {"key": {"bar": "bar"}},
        ),
        (
            GenDict[str, int],
            {"foo_bar": 2},
            {"fooBar": 2},
        ),
        (
            SerDict,
            {"foo_bar": 2},
            {"fooBar": 2},
        ),
        (
            objects.TDict,
            objects.TDict(a=1),
            {"a": "1"},
        ),
        (
            objects.NTup,
            objects.NTup(a=1),
            {"a": "1"},
        ),
        (
            ListUnion,
            ListUnion([MemberStr("string"), MemberInt(1)]),
            {"members": [{"field": "string"}, {"field": 1}]},
        ),
        (
            typing.Union[float, int, str],
            1.0,
            1.0,
        ),
        (
            typing.Union[float, int, str],
            1,
            1,
        ),
        (
            typing.Union[float, int, str],
            1.0,
            "1.0",
        ),
        (
            typing.Union[float, int, str],
            1,
            "1",
        ),
        (typing.Union[float, int, str], "foo", "foo"),
        (decimal.Decimal, decimal.Decimal("1000000000000000.3"), "1000000000000000.3"),
        (decimal.Decimal, decimal.Decimal("1000000000000000.25"), 1000000000000000.3),
        (objects.SubTypic, objects.SubTypic(var="", sub=""), {"var": "", "sub": ""}),
        (objects.TClass, objects.TClass(1), objects.NTup(1)),
    ],
)
def test_serde_deserialize(t, obj, prim):
    r = typic.resolver.resolve(t)
    assert r.deserialize(prim) == obj


@typic.klass
class Foo:
    bar: str
    id: Optional[typic.ReadOnly[int]] = ...


@typic.klass
class Bar:
    foos: List[Foo]


@pytest.mark.parametrize(
    argnames=("obj", "expected"),
    argvalues=[
        (None, b"null"),
        (MultiNum.INT, b"1"),
        (MultiNum.STR, b'"str"'),
        (
            {objects.FooNum.bar: objects.Typic(var="foo")},
            b'{"bar":{"var":"foo"}}',
        ),
        ([typic.URL("foo")], b'["foo"]'),
        (Omit(), b'{"bar":"foo"}'),
        (Bar(foos=[Foo("bar")]), b'{"foos":[{"bar":"bar","id":null}]}'),
    ],
)
def test_tojson(obj, expected):
    assert typic.tojson(obj, option=orjson.OPT_SORT_KEYS) == expected


@typic.klass
class Foo:
    bar: str
    id: Optional[typic.ReadOnly[int]] = None


@typic.klass
class Bar:
    foos: List[Foo]


@pytest.mark.parametrize(
    argnames=("obj", "expected"),
    argvalues=[
        (None, "null"),
        (MultiNum.INT, "1"),
        (MultiNum.STR, '"str"'),
        ([typic.URL("foo")], '["foo"]'),
        (Bar(foos=[Foo("bar")]), '{"foos":[{"bar":"bar","id":null}]}'),
    ],
)
def test_tojson_native(obj, expected):
    native = json.dumps(typic.primitive(obj)).replace("\n", "").replace(" ", "")
    assert typic.tojson(obj, option=orjson.OPT_SORT_KEYS).decode() == native == expected


badbar = Bar([])
badbar.foos.append("foo")


@pytest.mark.parametrize(
    argnames=("type", "value"),
    argvalues=[
        (str, 1),
        (bool, ""),
        (bytes, ""),
        (dict, []),
        (list, {}),
        (List[str], [1]),
        (Bar, Foo("")),
        (Bar, badbar),
        (Mapping[str, Bar], {"foo": Foo("")}),
        (List[Bar], [Foo("")]),
    ],
)
def test_invalid_serializer(type, value):
    proto = typic.protocol(type)
    with pytest.raises(ValueError):
        proto.tojson(value)


def test_inherited_serde_flags():
    @typic.klass(serde=typic.flags(omit=(1,)))
    class Foo:
        a: str
        b: str = typic.field(exclude=True)

    @typic.klass(serde=typic.flags(omit=(2,)))
    class Bar(Foo):
        c: int

    assert Bar.__serde_flags__.fields.keys() == {"a", "b", "c"}
    assert Bar.__serde_flags__.exclude == {"b"}
    assert Bar.__serde_flags__.omit == (1, 2)


def test_custom_encode():
    def encode(o):
        return ujson.encode(o).encode("utf-8-sig")

    @dataclasses.dataclass
    class Foo:
        bar: str = None

    proto = typic.protocol(Foo, flags=typic.flags(encoder=encode))
    enc = proto.encode(Foo())
    assert isinstance(enc, bytes)
    assert enc.decode("utf-8-sig") == '{"bar":null}'


def test_custom_decode():
    def decode(o):
        return o.decode("utf-8-sig")

    @dataclasses.dataclass
    class Foo:
        bar: str = None

    proto = typic.protocol(Foo, flags=typic.flags(decoder=decode))
    inp = '{"bar":null}'.encode("utf-8-sig")
    dec = proto.decode(inp)
    assert dec == Foo()


def test_klass_custom_encdec():
    def encode(o):
        return ujson.encode(o).encode("utf-8-sig")

    def decode(o):
        return o.decode("utf-8-sig")

    @typic.klass(serde=typic.flags(encoder=encode, decoder=decode))
    class Foo:
        bar: str = None

    enc = Foo().encode()
    dec = Foo.decode(enc)
    assert isinstance(enc, bytes)
    assert enc.decode("utf-8-sig") == '{"bar":null}'
    assert dec == Foo()


def test_functional_custom_encdec():
    def encode(o):
        return ujson.encode(o).encode("utf-8-sig")

    def decode(o):
        return o.decode("utf-8-sig")

    @dataclasses.dataclass
    class Foo:
        bar: str = None

    enc = typic.encode(Foo(), encoder=encode)
    dec = typic.decode(Foo, enc, decoder=decode)
    assert isinstance(enc, bytes)
    assert enc.decode("utf-8-sig") == '{"bar":null}'
    assert dec == Foo()


def test_proto_iterate():
    @dataclasses.dataclass
    class Foo:
        bar: str = None

    proto = typic.protocol(Foo)

    assert dict(proto.iterate(Foo())) == {"bar": None}
    assert [*proto.iterate(Foo(), values=True)] == [None]


def test_functional_iterate():
    @dataclasses.dataclass
    class Foo:
        bar: str = None

    assert dict(typic.iterate(Foo())) == {"bar": None}
    assert [*typic.iterate(Foo(), values=True)] == [None]


def test_klass_iterate():
    @typic.klass
    class Foo:
        bar: str = None

    assert dict(Foo().iterate()) == dict(Foo()) == {"bar": None}
    assert [*Foo().iterate(values=True)] == [None]


def test_iterate_slots():
    class Foo:
        __slots__ = ("bar",)

        def __init__(self):
            self.bar = "bar"

    assert dict(typic.iterate(Foo())) == {"bar": "bar"}


def test_functional_iterate_exclude():
    @dataclasses.dataclass
    class Foo:
        bar: str = None
        excluded: str = None

    assert dict(typic.iterate(Foo(), exclude=("excluded",))) == {"bar": None}


def test_protocol_iterate_exclude():
    @dataclasses.dataclass
    class Foo:
        bar: str = None
        excluded: str = None

    proto = typic.protocol(Foo, flags=typic.flags(exclude=("excluded",)))

    assert dict(proto.iterate(Foo())) == {"bar": None}


def test_klass_iterate_exclude():
    @typic.klass(serde=typic.flags(exclude=("excluded",)))
    class Foo:
        bar: str = None
        excluded: str = None

    assert dict(Foo().iterate()) == {"bar": None}


@pytest.mark.parametrize(
    argnames="v", argvalues=[1, objects.LargeInt(1001), 1.0, objects.LargeFloat(1000.5)]
)
def test_iterate_invalid(v):
    with pytest.raises(TypeError):
        typic.iterate(v)


def test_transmute_excluded():
    @dataclasses.dataclass
    class Foo:
        __serde_flags__ = typic.flags(exclude=("excluded",))
        bar: str = None
        excluded: bool = True

    @dataclasses.dataclass
    class Bar:
        bar: str = None
        excluded: bool = False

    assert typic.transmute(Bar, Foo()) == Bar()


def test_routine_protocol():
    def foo():
        ...

    proto = typic.protocol(foo)
    assert proto.transmute(foo) is foo
    assert proto.validate(foo) is foo
    with pytest.raises(TypeError):
        proto.serialize(foo)

    assert list(proto.iterate(foo)) == [None]
