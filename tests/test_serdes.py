#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import datetime
import decimal
import enum
import ipaddress
import json
import re
from types import MappingProxyType
from typing import ClassVar, Optional, Dict, TypeVar, Generic, List, Mapping

import pytest

import typic
import typic.api
import typic.common
import typic.ext.json
from tests import objects


@typic.klass
class FieldMapp:
    __serde_flags__ = typic.SerdeFlags(fields={"foo_bar": "foo"})

    foo_bar: str = "bar"


@typic.klass
class Camel:
    __serde_flags__ = typic.SerdeFlags(case=typic.common.Case.CAMEL)

    foo_bar: str = "bar"


@typic.klass
class SigOnly:
    __serde_flags__ = typic.SerdeFlags(signature_only=True)

    foo: ClassVar[str] = "foo"
    foo_bar: str = "bar"


@typic.klass
class Omit:
    __serde_flags__ = typic.SerdeFlags(omit=("bar",))

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
        (datetime.datetime(1970, 1, 1), "1970-01-01T00:00:00+00:00"),
        (
            datetime.datetime(
                1970, 1, 1, tzinfo=datetime.timezone(datetime.timedelta(hours=1))
            ),
            "1970-01-01T00:00:00+01:00",
        ),
        (objects.Typic(var="foo"), {"var": "foo"}),
        (objects.Data(foo="foo"), {"foo": "foo"}),
        (objects.FromDict(), {"foo": None}),
        (decimal.Decimal("1.0"), 1.0),
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
    __serde_flags__ = typic.SerdeFlags(
        fields=("foo_bar",), case=typic.common.Case.CAMEL
    )


class SerDict(Dict):
    __serde_flags__ = typic.SerdeFlags(
        fields=("foo_bar",), case=typic.common.Case.CAMEL
    )


class CaseDict(Dict):
    __serde_flags__ = typic.SerdeFlags(case=typic.common.Case.CAMEL)


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
        (GenDict[str, int], GenDict(foo_bar=2), {"fooBar": 2},),
        (SerDict, SerDict(foo_bar=2), {"fooBar": 2},),
        (CaseDict, CaseDict(foo_bar=2), {"fooBar": 2},),
    ],
)
def test_serde_serializer(t, obj, prim):
    r = typic.resolver.resolve(t)
    assert r.primitive(obj) == prim


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
        (GenDict[str, int], {"foo_bar": 2}, {"fooBar": 2},),
        (SerDict, {"foo_bar": 2}, {"fooBar": 2},),
    ],
)
def test_serde_deserializer(t, obj, prim):
    r = typic.resolver.resolve(t)
    assert r.deserializer(prim) == obj


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
        ({objects.FooNum.bar: objects.Typic(var="foo")}, '{"bar":{"var":"foo"}}',),
        ([typic.URL("foo")], '["foo"]'),
        (Omit(), '{"bar":"foo"}'),
        (Bar(foos=[Foo("bar")]), '{"foos":[{"bar":"bar","id":null}]}'),
    ],
)
def test_tojson(obj, expected):
    assert typic.tojson(obj) == expected


typic.ext.json.NATIVE_JSON = True


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
    native = (
        json.dumps(typic.primitive(obj, lazy=True)).replace("\n", "").replace(" ", "")
    )
    assert typic.tojson(obj) == native == expected


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
