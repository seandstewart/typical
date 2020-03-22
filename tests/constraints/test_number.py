#!/usr/bin/env python
from decimal import Decimal
from typing import Type

import pytest

from typic.constraints import (
    IntContraints,
    FloatContraints,
    DecimalContraints,
    ConstraintValueError,
    ConstraintSyntaxError,
)
from typic.constraints.common import BaseConstraints


@pytest.mark.parametrize(
    argnames=("val", "constraint", "expected"),
    argvalues=[
        (0, IntContraints(), 0),
        (1, IntContraints(gt=0), 1),
        (2, IntContraints(ge=2), 2),
        (3, IntContraints(lt=4), 3),
        (4, IntContraints(le=4), 4),
        (5, IntContraints(mul=5), 5),
        (0.0, FloatContraints(), 0.0),
        (1.0, FloatContraints(gt=0), 1.0),
        (2.0, FloatContraints(ge=2), 2.0),
        (3.0, FloatContraints(lt=4), 3.0),
        (4.0, FloatContraints(le=4), 4.0),
        (5.0, FloatContraints(mul=5), 5.0),
        (Decimal(0.0), DecimalContraints(), 0.0),
        (Decimal(1.0), DecimalContraints(gt=0), 1.0),
        (Decimal(2.0), DecimalContraints(ge=2), 2.0),
        (Decimal(3.0), DecimalContraints(lt=4), 3.0),
        (Decimal(4.0), DecimalContraints(le=4), 4.0),
        (Decimal(5.0), DecimalContraints(mul=5), 5.0),
        (Decimal(6.0), DecimalContraints(max_digits=2), 6.0),
        (Decimal(7.0), DecimalContraints(decimal_places=2), 7.0),
        (
            Decimal("0.7"),
            DecimalContraints(decimal_places=2, max_digits=2),
            Decimal("0.7"),
        ),
    ],
)
def test_validate_values(val: str, constraint: IntContraints, expected: str):
    assert constraint.validate(val) == expected


@pytest.mark.parametrize(
    argnames=("val", "constraint", "expected"),
    argvalues=[
        (0, IntContraints(gt=0), ConstraintValueError),
        (1, IntContraints(ge=2), ConstraintValueError),
        (2, IntContraints(lt=2), ConstraintValueError),
        (3, IntContraints(le=2), ConstraintValueError),
        (0.0, FloatContraints(gt=0), ConstraintValueError),
        (1.0, FloatContraints(ge=2), ConstraintValueError),
        (2.0, FloatContraints(lt=2), ConstraintValueError),
        (3.0, FloatContraints(le=2), ConstraintValueError),
        (Decimal(1.0), DecimalContraints(gt=1), ConstraintValueError),
        (Decimal(1.0), DecimalContraints(ge=2), ConstraintValueError),
        (Decimal(4.0), DecimalContraints(lt=4), ConstraintValueError),
        (Decimal(5.0), DecimalContraints(le=4), ConstraintValueError),
        (Decimal(6.0), DecimalContraints(mul=5), ConstraintValueError),
        (Decimal("60.0"), DecimalContraints(max_digits=2), ConstraintValueError),
        (Decimal("7.000"), DecimalContraints(decimal_places=2), ConstraintValueError),
    ],
)
def test_validate_values_error(val: str, constraint: IntContraints, expected: str):
    with pytest.raises(expected):
        constraint.validate(val)


@pytest.mark.parametrize(
    argnames=("constraint", "kwargs"),
    argvalues=[
        (IntContraints, dict(gt=2, ge=2)),
        (IntContraints, dict(lt=2, le=2)),
        (IntContraints, dict(lt=2, gt=2)),
        (IntContraints, dict(lt=2, ge=2)),
        (DecimalContraints, dict(max_digits=1, decimal_places=2)),
    ],
)
def test_constraint_syntax_error(constraint: Type[BaseConstraints], kwargs: dict):
    with pytest.raises(ConstraintSyntaxError):
        constraint(**kwargs)


@pytest.mark.parametrize(
    argnames=("val", "constraint", "expected"),
    argvalues=[
        (1, IntContraints(gt=0, lt=2), 1),
        (Decimal(7.0), DecimalContraints(gt=1, max_digits=3, decimal_places=2), 7.0),
    ],
)
def test_validate_values_complex(val: str, constraint: IntContraints, expected: str):
    assert constraint.validate(val) == expected
