from __future__ import annotations

import pytest

from typical import constraints


def test_constrained_new():
    # Given
    @constraints.constrained(max_length=10)
    class ShortStr(str):
        ...

    # When/Then
    with pytest.raises(constraints.error.ConstraintValueError):
        ShortStr("1234567891011")


def test_constrained_init():
    # Given
    @constraints.constrained(max_items=1)
    class SmallMap(dict):
        ...

    # When/Then
    with pytest.raises(constraints.error.ConstraintValueError):
        SmallMap({"foo": 1, "bar": 2})


def test_constrained_builtin():
    # Given
    ShortStr = constraints.constrained(str, max_length=10)
    # When/Then
    with pytest.raises(constraints.error.ConstraintValueError):
        ShortStr("1234567891011")


def test_nested_constraints():
    # Given
    @constraints.constrained(max_length=10)
    class ShortStr(str):
        ...

    @constraints.constrained(max_items=1, values=ShortStr, keys=ShortStr)
    class SmallMap(dict):
        ...

    # When/Then
    with pytest.raises(constraints.error.ConstraintValueError):
        SmallMap({"foo": 1})
