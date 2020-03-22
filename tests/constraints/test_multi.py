#!/usr/bin/env python
import pytest

from typic.constraints import (
    MultiConstraints,
    StrConstraints,
    IntContraints,
)


@pytest.mark.parametrize(
    argnames=("constraints", "types"),
    argvalues=[
        (MultiConstraints(constraints=(StrConstraints(), IntContraints())), {str, int}),
        (
            MultiConstraints(
                constraints=(
                    MultiConstraints(constraints=(StrConstraints(), IntContraints())),
                    StrConstraints(),
                )
            ),
            {str, int},
        ),
    ],
)
def test_multi_type(constraints, types):
    assert {*constraints.type} == types


def test_empty():
    passed, val = MultiConstraints(()).validator("foo")
    assert passed
