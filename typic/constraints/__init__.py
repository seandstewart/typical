#!/usr/bin/env python
# -*- coding: UTF-8 -*-

# flake8: noqa
from typing import Union

from .array import ListContraints, TupleContraints, SetContraints, FrozenSetConstraints
from .common import Validator, BaseConstraints
from .error import ConstraintValueError, ConstraintSyntaxError
from .mapping import DictConstraints
from .number import DecimalContraints, FloatContraints, IntContraints, Number
from .text import BytesConstraints, StrConstraints

Constraints = Union[
    BytesConstraints,
    DecimalContraints,
    DictConstraints,
    FloatContraints,
    FrozenSetConstraints,
    IntContraints,
    ListContraints,
    SetContraints,
    StrConstraints,
    TupleContraints,
]


__all__ = (
    "ConstraintValueError",
    "ConstraintSyntaxError",
    "BytesConstraints",
    "Constraints",
    "DecimalContraints",
    "DictConstraints",
    "FloatContraints",
    "FrozenSetConstraints",
    "IntContraints",
    "ListContraints",
    "Number",
    "SetContraints",
    "StrConstraints",
    "TupleContraints",
    "Validator",
    "BaseConstraints",
)
