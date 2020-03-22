#!/usr/bin/env python
import dataclasses

import pytest

from typic.constraints import (
    ListContraints,
    StrConstraints,
    IntContraints,
    ConstraintValueError,
)


@dataclasses.dataclass
class Foo:
    bar: str = "bar"


@pytest.mark.parametrize(
    argnames=("val", "constraint", "expected"),
    argvalues=[
        ([], ListContraints(), []),
        ([1], ListContraints(min_items=1), [1]),
        ([1, 2], ListContraints(max_items=2), [1, 2]),
        ([1, 2, 2], ListContraints(unique=True), [1, 2]),
        ([Foo(), Foo(), 2], ListContraints(unique=True), [Foo(), 2]),
    ],
)
def test_validate_values(val: str, constraint: ListContraints, expected: list):
    assert constraint.validate(val) == expected


@pytest.mark.parametrize(
    argnames=("val", "constraint", "expected"),
    argvalues=[
        ([], ListContraints(min_items=1), ConstraintValueError),
        ([1, 2, 3], ListContraints(max_items=2), ConstraintValueError),
    ],
)
def test_validate_values_error(
    val: str, constraint: ListContraints, expected: Exception
):
    with pytest.raises(expected):
        constraint.validate(val)


@pytest.mark.parametrize(
    argnames=("val", "constraint", "expected"),
    argvalues=[
        ([1, 2], ListContraints(min_items=1, max_items=2), [1, 2]),
        ([1, 2, 2], ListContraints(unique=True, max_items=2), [1, 2]),
    ],
)
def test_validate_values_multi(val: str, constraint: ListContraints, expected: list):
    assert constraint.validate(val) == expected


@pytest.mark.parametrize(
    argnames=("val", "constraint", "expected"),
    argvalues=[
        (
            [1, 2],
            ListContraints(min_items=1, max_items=2, values=IntContraints(ge=1)),
            [1, 2],
        ),
        (
            ["foo "],
            ListContraints(
                min_items=1,
                max_items=2,
                values=StrConstraints(strip_whitespace=True, min_length=2),
            ),
            ["foo"],
        ),
    ],
)
def test_validate_values_nested_constraints(
    val: str, constraint: ListContraints, expected: list
):
    assert constraint.validate(val) == expected
