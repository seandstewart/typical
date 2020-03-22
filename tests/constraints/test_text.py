#!/usr/bin/env python
import re

import pytest

from typic.constraints import StrConstraints, ConstraintValueError


@pytest.mark.parametrize(
    argnames=("val", "constraint", "expected"),
    argvalues=[
        ("", StrConstraints(), ""),
        ("foo ", StrConstraints(strip_whitespace=True), "foo"),
        ("min", StrConstraints(min_length=1), "min"),
        ("max", StrConstraints(max_length=3), "max"),
        ("cur", StrConstraints(curtail_length=2), "cu"),
        ("re", StrConstraints(regex=re.compile(r"\w+")), "re"),
    ],
)
def test_validate_values(val: str, constraint: StrConstraints, expected: str):
    assert constraint.validate(val) == expected


@pytest.mark.parametrize(
    argnames=("val", "constraint", "expected"),
    argvalues=[
        ("", StrConstraints(min_length=1), ConstraintValueError),
        ("maxi", StrConstraints(max_length=3), ConstraintValueError),
        (" ", StrConstraints(regex=re.compile(r"\w+")), ConstraintValueError),
    ],
)
def test_validate_values_error(val: str, constraint: StrConstraints, expected: str):
    with pytest.raises(expected):
        constraint.validate(val)


@pytest.mark.parametrize(
    argnames=("val", "constraint", "expected"),
    argvalues=[
        ("foo ", StrConstraints(strip_whitespace=True, max_length=3), "foo"),
        (
            "foobar ",
            StrConstraints(strip_whitespace=True, max_length=3, curtail_length=3),
            "foo",
        ),
        (
            "foo bar ",
            StrConstraints(
                strip_whitespace=True,
                max_length=3,
                curtail_length=3,
                regex=re.compile(r"\w+"),
            ),
            "foo",
        ),
    ],
)
def test_validate_values_complex(val: str, constraint: StrConstraints, expected: str):
    assert constraint.validate(val) == expected
