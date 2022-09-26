from __future__ import annotations

import dataclasses
import datetime
import typing

import pytest

import typic
from typic.core.constraints.factory import factory


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
        (typing.Union[int, str], 1),
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
    c = factory.build(t)
    assert c.validate(v) == v


@pytest.mark.parametrize(
    argnames=("t", "v"),
    argvalues=[
        (str, 1),
        (int, ""),
        (float, ""),
        (dict, []),
        (list, {}),
        (tuple, ""),
        (frozenset, ""),
        (typing.Dict[str, int], {"foo": ""}),
        (typing.List[int], [""]),
        (typing.Union[int, str], []),
        (typing.List[typing.Optional[typing.Dict[str, int]]], [[]]),
        (typing.List[typing.Optional[typing.Dict[str, int]]], [{"foo": ""}]),
        (Foo, {"bar": 1}),
        (Foo, {"bar": "", "unknown": 1}),
        (typing.Optional[Foo], {"bar": 1}),
        (typing.Optional[Foo], 1),
        (
            typing.List[typing.Optional[typing.Union[Foo, typing.Dict[str, int]]]],
            [[]],
        ),
        (
            typing.List[typing.Optional[typing.Union[Foo, typing.Dict[str, int]]]],
            [""],
        ),
        (
            typing.List[typing.Optional[typing.Union[Foo, typing.Dict[str, int]]]],
            [{"bar": ""}],
        ),
        (MyStr, 1),
    ],
    ids=[
        "str-wrong-type",
        "int-wrong-type",
        "float-wrong-type",
        "dict-wrong-type",
        "list-wrong-type",
        "tuple-wrong-type",
        "frozenset-wrong-type",
        "dict-str-int-wrong-value-type",
        "list-int-wrong-value-type",
        "union-str-int-wrong-value-type",
        "list-optional-dict-str-int-wrong-list-value-type",
        "list-optional-dict-str-int-wrong-dict-value-type",
        "structured-wrong-field-type",
        "structured-unknown-field",
        "optional-structured-wrong-field-type",
        "optional-structured-wrong-type",
        "list-optional-union-structured-dict-wrong-list-value-type",
        "list-optional-union-structured-dict-wrong-list-value-type-2",
        "list-optional-union-structured-dict-wrong-dict-value-type-2",
        "custom-str-wrong-type",
    ],
)
def test_get_contraints_invalid(t, v):
    c = factory.build(t)
    with pytest.raises(typic.constraints.error.ConstraintValueError):
        c.validate(v)
