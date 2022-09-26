from __future__ import annotations

import decimal
import functools
import numbers
from typing import Any, NamedTuple, TypeVar

from typic.core.constraints.core import assertions, error
from typic.core.constraints.number import assertions as number

__all__ = (
    "get_assertion_cls",
    "AbstractDecimalAssertion",
    "MaxDecimalsAssertion",
    "MaxDigitsAssertion",
    "MaxDigitsAndDecimalsAssertion",
)


@functools.lru_cache(maxsize=None)
def get_assertion_cls(
    *,
    has_min: bool,
    has_max: bool,
    inclusive_min: bool,
    inclusive_max: bool,
    has_mul: bool,
    has_max_digits: bool,
    has_max_decimals: bool,
) -> tuple[type[AbstractDecimalAssertion], type[number.AbstractNumberAssertion]] | None:
    number_assertion = number.get_assertion_cls(
        has_min=has_min,
        has_max=has_max,
        inclusive_min=inclusive_min,
        inclusive_max=inclusive_max,
        has_mul=has_mul,
    )
    if not number_assertion:
        return None
    selector = DecimalAssertionsSelector(
        has_max_digits=has_max_digits, has_max_decimals=has_max_decimals
    )
    if not any(selector):
        return None
    return _ASSERTION_TRUTH_TABLE[selector], number_assertion


class DecimalAssertionsSelector(NamedTuple):
    has_max_digits: bool
    has_max_decimals: bool


_DT = TypeVar("_DT", bound=decimal.Decimal)


class AbstractDecimalAssertion(assertions.AbstractAssertions[_DT]):
    selector: DecimalAssertionsSelector

    __slots__ = (
        "number_assertions",
        "max_digits",
        "max_decimal_places",
        "max_whole_digits",
    )

    def __repr__(self):
        return (
            "<"
            f"{self.__class__.__name__}("
            f"min={self.number_assertions.min!r}, "
            f"max={self.number_assertions.max!r}, "
            f"mul={self.number_assertions.mul!r}, "
            f"max_digits={self.max_digits!r}, "
            f"max_decimal_places={self.max_decimal_places!r}, "
            f"max_whole_digits={self.max_whole_digits!r}"
            ")>"
        )

    def __init__(
        self,
        *,
        number_assertions: number.AbstractNumberAssertion[_DT] = None,  # type: ignore[type-var]
        max_digits: numbers.Real = None,
        max_decimal_places: numbers.Real = None,
    ):
        self.number_assertions = number_assertions
        self.max_digits = max_digits
        self.max_decimal_places = max_decimal_places
        self.max_whole_digits = None
        if (max_digits, max_decimal_places) != (None, None):
            self.max_whole_digits = max_digits - max_decimal_places
        self._check_syntax()
        super().__init__()

    def _check_syntax(self):
        if self.max_digits < self.max_decimal_places:
            msg = (
                f"Contraint <max_decimal_places={self.max_decimal_places!r}> "
                f"should never be greater than "
                f"Constraint <max_digits={self.max_digits!r}>"
            )
            raise error.ConstraintSyntaxError(msg) from None

    @staticmethod
    @functools.lru_cache(maxsize=2000)
    def _get_digits(number: decimal.Decimal) -> tuple[int, int, int]:
        tup = number.as_tuple()
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


class MaxDigitsAssertion(AbstractDecimalAssertion[_DT]):
    selector = DecimalAssertionsSelector(has_max_digits=True, has_max_decimals=False)

    def _get_closure(self) -> assertions.AssertionProtocol[_DT]:
        def max_digits_assertion(
            val: Any,
            *,
            __max_digits=self.max_digits,
            __digits=self._get_digits,
            __number_assertions=self.number_assertions,
        ) -> bool:
            whole_digits, all_digits, decimal_places = __digits(val)
            return all_digits <= __max_digits and __number_assertions(val)

        return max_digits_assertion


class MaxDecimalsAssertion(AbstractDecimalAssertion[_DT]):
    selector = DecimalAssertionsSelector(has_max_digits=False, has_max_decimals=True)

    def _get_closure(self) -> assertions.AssertionProtocol[_DT]:
        def max_decimals_assertion(
            val: Any,
            *,
            __max_decimal_places=self.max_decimal_places,
            __digits=self._get_digits,
            __number_assertions=self.number_assertions,
        ) -> bool:
            whole_digits, all_digits, decimal_places = __digits
            return decimal_places <= __max_decimal_places and __number_assertions(val)

        return max_decimals_assertion


class MaxDigitsAndDecimalsAssertion(AbstractDecimalAssertion[_DT]):
    selector = DecimalAssertionsSelector(has_max_digits=True, has_max_decimals=True)

    def _get_closure(self) -> assertions.AssertionProtocol[_DT]:
        def max_digits_and_decimals_assertion(
            val: Any,
            *,
            __max_digits=self.max_digits,
            __max_decimal_places=self.max_decimal_places,
            __max_whole_digits=self.max_whole_digits,
            __get_digits=self._get_digits,
            __number_assertions=self.number_assertions,
        ) -> bool:
            whole_digits, all_digits, decimal_places = __get_digits(val)
            return (
                all_digits <= __max_digits
                and decimal_places <= __max_decimal_places
                and whole_digits <= __max_whole_digits
                and __number_assertions(val)
            )

        return max_digits_and_decimals_assertion


_ASSERTION_TRUTH_TABLE: dict[
    DecimalAssertionsSelector, type[AbstractDecimalAssertion]
] = {
    MaxDecimalsAssertion.selector: MaxDecimalsAssertion,
    MaxDigitsAssertion.selector: MaxDigitsAssertion,
    MaxDigitsAndDecimalsAssertion.selector: MaxDigitsAndDecimalsAssertion,
}
