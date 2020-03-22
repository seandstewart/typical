#!/usr/bin/env python
import dataclasses
import decimal
from typing import Union, Type, ClassVar, Optional, Dict

from .builder import _build_validator
from ..common import BaseConstraints

Number = Union[int, float, decimal.Decimal]


@dataclasses.dataclass(frozen=True, repr=False)
class NumberConstraints(BaseConstraints):
    """Specific constraints pertaining to number-like types.

    Currently supports :py:class:`int`, :py:class:`float`, and
    :py:class:`decimal.Decimal`.

    See Also
    --------
    :py:class:`~typic.types.constraints.common.BaseConstraints`
    """

    type: ClassVar[Type[Number]]
    builder = _build_validator
    """The builtin type for this constraint."""
    gt: Optional[Number] = None
    """The value inputs must be greater-than."""
    ge: Optional[Number] = None
    """The value inputs must be greater-than-or-equal-to."""
    lt: Optional[Number] = None
    """The value inputs must be less-than."""
    le: Optional[Number] = None
    """The value inputs must be less-than-or-equal-to."""
    mul: Optional[Number] = None
    """The value inputs must be a multiple-of."""

    def for_schema(self, *, with_type: bool = False) -> dict:
        schema: Dict[str, Union[None, Number, str]] = dict(
            multipleOf=self.mul,
            minimum=self.ge,
            maximum=self.le,
            exclusiveMinimum=self.gt,
            exclusiveMaximum=self.lt,
        )
        if with_type:
            schema["type"] = "number"
        return {x: y for x, y in schema.items() if y is not None}


@dataclasses.dataclass(frozen=True, repr=False)
class IntContraints(NumberConstraints):
    """Constraints specifically for :py:class:`int`.

    See Also
    --------
    :py:class:`NumberConstraints`
    """

    type: ClassVar[Type[Number]] = int

    def for_schema(self, *, with_type: bool = False) -> dict:
        schema = super().for_schema()
        if with_type:
            schema["type"] = "integer"
        return schema


@dataclasses.dataclass(frozen=True, repr=False)
class FloatContraints(NumberConstraints):
    """Constraints specifically for :py:class:`int`.

    See Also
    --------
    :py:class:`NumberConstraints`
    """

    type: ClassVar[Type[Number]] = float


@dataclasses.dataclass(frozen=True, repr=False)
class DecimalContraints(NumberConstraints):
    """Constraints specifically for :py:class:`int`.

    See Also
    --------
    :py:class:`NumberConstraints`
    """

    type: ClassVar[Type[Number]] = decimal.Decimal
    max_digits: Optional[int] = None
    """The maximum allowed digits for the input."""
    decimal_places: Optional[int] = None
    """The maximum allowed decimal places for the input."""
