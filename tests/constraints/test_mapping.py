#!/usr/bin/env python
import dataclasses
import re
from typing import Type

import pytest

from typic.constraints import (
    DictConstraints,
    StrConstraints,
    IntContraints,
    ConstraintValueError,
    ConstraintSyntaxError,
)
from typic.types import FrozenDict

EMPTY: dict = {}
FOO = {"foo": 1}
BAR = {"bar": 2}
FOOBAR = {"foo": 1, "bar": 2}
FPATT = re.compile(r"^f.+")


@dataclasses.dataclass
class Foo:
    bar: str = "bar"


@pytest.mark.parametrize(
    argnames=("val", "constraint", "expected"),
    argvalues=[
        (EMPTY, DictConstraints(), EMPTY),
        (FOO, DictConstraints(min_items=1), FOO),
        (FOOBAR, DictConstraints(max_items=2), FOOBAR),
        (FOOBAR, DictConstraints(required_keys=frozenset(("foo",))), FOOBAR),
        (FOO, DictConstraints(key_pattern=FPATT), FOO),
        (FOO, DictConstraints(patterns=FrozenDict({FPATT: IntContraints(ge=1)})), FOO),
        (FOO, DictConstraints(items=FrozenDict({"foo": IntContraints(ge=1)})), FOO),
        (FOOBAR, DictConstraints(key_dependencies=FrozenDict(foo=["bar"])), FOOBAR),
        (
            FOOBAR,
            DictConstraints(
                min_items=1,
                key_dependencies=FrozenDict(
                    foo=DictConstraints(required_keys=frozenset(["bar"]))
                ),
            ),
            FOOBAR,
        ),
    ],
)
def test_validate_keys(val: str, constraint: DictConstraints, expected: list):
    assert constraint.validate(val) == expected


@pytest.mark.parametrize(
    argnames=("val", "constraint", "expected"),
    argvalues=[
        (EMPTY, DictConstraints(min_items=1), ConstraintValueError),
        (FOOBAR, DictConstraints(max_items=1), ConstraintValueError),
        (BAR, DictConstraints(required_keys=frozenset(("foo",))), ConstraintValueError),
        (BAR, DictConstraints(key_pattern=FPATT), ConstraintValueError),
        (
            FOOBAR,
            DictConstraints(required_keys=frozenset(("foo",)), total=True),
            ConstraintValueError,
        ),
        (
            FOOBAR,
            DictConstraints(values=StrConstraints(min_length=1)),
            ConstraintValueError,
        ),
        (
            FOOBAR,
            DictConstraints(
                items=FrozenDict({"foo": IntContraints(ge=1)}),
                values=StrConstraints(min_length=1),
            ),
            ConstraintValueError,
        ),
        (
            FOO,
            DictConstraints(patterns=FrozenDict({FPATT: StrConstraints(min_length=1)})),
            ConstraintValueError,
        ),
        (
            FOO,
            DictConstraints(patterns=FrozenDict({FPATT: StrConstraints(min_length=1)})),
            ConstraintValueError,
        ),
    ],
)
def test_validate_keys_error(
    val: str, constraint: DictConstraints, expected: Type[Exception]
):
    with pytest.raises(expected):
        constraint.validate(val)


@pytest.mark.parametrize(
    argnames=("kwargs",),
    argvalues=[
        (dict(key_dependencies=FrozenDict(foo="bar")),),
        (dict(keys=StrConstraints(), total=True),),
    ],
)
def test_syntax_error(kwargs):
    with pytest.raises(ConstraintSyntaxError):
        DictConstraints(**kwargs)
