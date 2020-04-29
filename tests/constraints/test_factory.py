#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import dataclasses
import datetime
import typing

import pytest

import typic
from typic.constraints.factory import get_constraints


@dataclasses.dataclass
class Foo:
    bar: str


class MyStr(str):
    ...


class MyURL(typic.URL):
    ...


@pytest.mark.parametrize(
    argnames=("t", "v"),
    argvalues=[
        (str, ""),
        (int, 0),
        (float, 0.0),
        (dict, {}),
        (list, []),
        (tuple, ()),
        (frozenset, frozenset({})),
        (typing.Dict[str, int], {"foo": 1}),
        (typing.List[int], [1]),
        (typing.Union[str, int], 1),
        (typing.List[typing.Optional[typing.Dict[str, int]]], [None]),
        (typing.List[typing.Optional[typing.Dict[str, int]]], [{"foo": 1}]),
        (Foo, {"bar": "bar"}),
        (typing.Optional[Foo], {"bar": "bar"}),
        (typing.Optional[Foo], None),
        (
            typing.List[typing.Optional[typing.Union[Foo, typing.Dict[str, int]]]],
            [None],
        ),
        (
            typing.List[typing.Optional[typing.Union[Foo, typing.Dict[str, int]]]],
            [Foo("")],
        ),
        (
            typing.List[typing.Optional[typing.Union[Foo, typing.Dict[str, int]]]],
            [{"bar": 1}],
        ),
        (datetime.datetime, datetime.datetime.now()),
        (typing.Optional[datetime.datetime], datetime.datetime.now()),
        (typing.Optional[datetime.datetime], None),
        (MyStr, MyStr()),
        (MyURL, MyURL("foo.com")),
    ],
)
def test_get_contraints(t, v):
    c = get_constraints(t)
    assert c.validate(v) == v
