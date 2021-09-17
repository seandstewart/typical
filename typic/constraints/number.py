from __future__ import annotations

import dataclasses
import decimal
from typing import Union, Type, ClassVar, Optional, Dict, List

from typic import gen, util
from .common import BaseConstraints, ContextT, AssertionsT
from .error import ConstraintSyntaxError, ConstraintValueError

NumberT = Union[int, float, decimal.Decimal]


def _get_digits(tup: decimal.DecimalTuple):
    if tup.exponent >= 0:
        # A positive exponent adds that many trailing zeros.
        digits = len(tup.digits) + tup.exponent
        decimals = 0
    else:
        # If the absolute value of the negative exponent is larger than the
        # number of digits, then it's the same as the number of digits,
        # because it'll consume all of the digits in digit_tuple and then
        # add abs(exponent) - len(digit_tuple) leading zeros after the
        # decimal point.
        if abs(tup.exponent) > len(tup.digits):
            digits = decimals = abs(tup.exponent)
        else:
            digits = len(tup.digits)
            decimals = abs(tup.exponent)
    whole_digits = digits - decimals
    return whole_digits, digits, decimals


@util.slotted
@dataclasses.dataclass(frozen=True, repr=False)
class NumberConstraints(BaseConstraints):
    """Specific constraints pertaining to number-like types.

    Currently supports :py:class:`int`, :py:class:`float`, and
    :py:class:`decimal.Decimal`.

    See Also
    --------
    :py:class:`~typic.types.constraints.common.BaseConstraints`
    """

    type: ClassVar[Type[NumberT]]
    """The builtin type for this constraint."""
    gt: Optional[NumberT] = None
    """The value inputs must be greater-than."""
    ge: Optional[NumberT] = None
    """The value inputs must be greater-than-or-equal-to."""
    lt: Optional[NumberT] = None
    """The value inputs must be less-than."""
    le: Optional[NumberT] = None
    """The value inputs must be less-than-or-equal-to."""
    mul: Optional[NumberT] = None
    """The value inputs must be a multiple-of."""

    def _check_syntax(self):
        if self.gt is not None:
            if self.ge is not None:
                raise ConstraintSyntaxError(
                    "Values must either be '>' or '>=', not both."
                ) from None
            if self.gt in {self.lt, self.le}:
                msg = (
                    f"Values for '>' and '<|<=' are equal ({self.gt}, {self.lt}|{self.le}), "
                    f"this will always be false."
                )
                raise ConstraintSyntaxError(msg) from None
        if self.lt is not None:
            if self.le is not None:
                raise ConstraintSyntaxError(
                    "Values must either be '<' or '<=', not both."
                ) from None
            if self.lt in {self.gt, self.ge}:
                msg = (
                    f"Values for '<' and '>|>=' are equal ({self.lt}, {self.gt}|{self.ge}), "
                    f"this will always be false."
                )
                raise ConstraintSyntaxError(msg) from None

    def _get_assertions(self) -> AssertionsT:
        asserts: List[str] = []
        if self.gt is not None:
            asserts.append(f"{self.VALUE} > {self.gt}")
        if self.ge is not None:
            asserts.append(f"{self.VALUE} >= {self.ge}")
        if self.lt is not None:
            asserts.append(f"{self.VALUE} < {self.lt}")
        if self.le is not None:
            asserts.append(f"{self.VALUE} <= {self.le}")
        if self.mul is not None:
            asserts.append(f"{self.VALUE} % {self.mul} == 0")
        return asserts

    def for_schema(self, *, with_type: bool = False) -> dict:
        schema: Dict[str, Union[None, NumberT, str]] = dict(
            title=self.name,
            multipleOf=self.mul,
            minimum=self.ge,
            maximum=self.le,
            exclusiveMinimum=self.gt,
            exclusiveMaximum=self.lt,
        )
        if with_type:
            schema["type"] = "number"
        return {x: y for x, y in schema.items() if y is not None}


@util.slotted
@dataclasses.dataclass(frozen=True, repr=False)
class IntContraints(NumberConstraints):
    """Constraints specifically for :py:class:`int`.

    See Also
    --------
    :py:class:`NumberConstraints`
    """

    type: ClassVar[Type[NumberT]] = int

    def for_schema(self, *, with_type: bool = False) -> dict:
        schema = NumberConstraints.for_schema(self)
        if with_type:
            schema["type"] = "integer"
        return schema


@util.slotted
@dataclasses.dataclass(frozen=True, repr=False)
class FloatContraints(NumberConstraints):
    """Constraints specifically for :py:class:`int`.

    See Also
    --------
    :py:class:`NumberConstraints`
    """

    type: ClassVar[Type[NumberT]] = float


@util.slotted
@dataclasses.dataclass(frozen=True, repr=False)
class DecimalContraints(NumberConstraints):
    """Constraints specifically for :py:class:`int`.

    See Also
    --------
    :py:class:`NumberConstraints`
    """

    type: ClassVar[Type[NumberT]] = decimal.Decimal
    max_digits: Optional[int] = None
    """The maximum allowed digits for the input."""
    decimal_places: Optional[int] = None
    """The maximum allowed decimal places for the input."""

    def _check_syntax(self):
        NumberConstraints._check_syntax(self)
        if None in {self.max_digits, self.decimal_places}:
            return
        if self.max_digits < self.decimal_places:
            msg = (
                f"Contraint <decimal_places={self.decimal_places!r}> "
                f"should never be greater than "
                f"Constraint <max_digits={self.max_digits!r}>"
            )
            raise ConstraintSyntaxError(msg) from None

    def _get_assertions(self) -> AssertionsT:
        asserts = NumberConstraints._get_assertions(self)
        if (self.max_digits, self.decimal_places) == (None, None):
            return asserts

        if self.max_digits is not None:
            asserts.append(f"digits <= {self.max_digits}")
        if self.decimal_places is not None:
            asserts.append(f"decimals <= {self.decimal_places}")
        if self.decimal_places is not None and self.max_digits is not None:
            asserts.append(f"whole <= ({self.max_digits} - {self.decimal_places})")
        return asserts

    def _build_validator(
        self, func: gen.Block, context: ContextT, assertions: AssertionsT
    ) -> ContextT:
        if (self.max_digits, self.decimal_places) == (None, None):
            context = NumberConstraints._build_validator(
                self, func, context=context, assertions=assertions
            )
            context.update(
                decimal=decimal, Decimal=decimal.Decimal, _get_digits=_get_digits
            )
            return context
        # Update the global namespace for the validator
        # Add setup/sanity checks for decimals.
        func.l(f"{self.VALUE} = decimal.Decimal({self.VALUE})")
        with func.b(
            f"if {self.VALUE}.is_infinite():",
            ConstraintValueError=ConstraintValueError,
        ) as b:
            b.l("raise ConstraintValueError('Cannot validate infinite values.')")
        func.l(f"tup = {self.VALUE}.as_tuple()")
        func.l(
            "whole, digits, decimals = _get_digits(tup)",
            _get_digits=_get_digits,
        )
        context = NumberConstraints._build_validator(
            self, func, context=context, assertions=assertions
        )
        context.update(
            decimal=decimal, Decimal=decimal.Decimal, _get_digits=_get_digits
        )
        return context
