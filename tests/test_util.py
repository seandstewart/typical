#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import datetime
import decimal
import ipaddress
import re
from types import MappingProxyType

import pytest

import typic
import typic.util
from tests import objects


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
    ],
)
def test_primitive(obj, expected):
    primitive = typic.util.primitive(obj)
    assert repr(primitive) == repr(expected)
    assert isinstance(primitive, type(expected))


@pytest.mark.parametrize(argnames=("obj",), argvalues=[(objects.Class(var="foo"),)])
def test_primitive_error(obj):
    with pytest.raises(ValueError):
        typic.util.primitive(obj)
