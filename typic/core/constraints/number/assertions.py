from __future__ import annotations

import functools
import numbers
from typing import NamedTuple, TypeVar

from typic.core.constraints.core import assertions, error

__all__ = (
    "get_assertion_cls",
    "AbstractNumberAssertion",
    "NumberAssertionsSelector",
    "MulOfAssertion",
    "InclusiveMaxAssertion",
    "InclusiveMaxAndMulOfAssertion",
    "ExclusiveMaxAssertion",
    "InclusiveMinAssertion",
    "InclusiveMinAndMulOfAssertion",
    "InclusiveRangeAssertion",
    "InclusiveRangeAndMulOfAssertion",
    "LeftInclusiveRangeAssertion",
    "LeftInclusiveRangeAndMulOfAssertion",
    "ExclusiveMinAssertion",
    "ExclusiveMinAndMulOfAssertion",
    "RightInclusiveRangeAssertion",
    "RightInclusiveRangeAndMulOfAssertion",
    "ExclusiveRangeAssertion",
    "ExclusiveRangeAndMulOfAssertion",
)


@functools.lru_cache(maxsize=None)
def get_assertion_cls(
    *,
    has_min: bool,
    inclusive_min: bool,
    has_max: bool,
    inclusive_max: bool,
    has_mul: bool,
) -> type[AbstractNumberAssertion] | None:
    selector = NumberAssertionsSelector(
        exclusive_min=has_min and not inclusive_min,
        inclusive_min=has_min and inclusive_min,
        exclusive_max=has_max and not inclusive_max,
        inclusive_max=has_max and inclusive_max,
        has_mul=has_mul,
    )
    if not any(selector):
        return None
    if selector in _ILLEGAL_COMBINATIONS:
        raise error.ConstraintTypeError(
            "Exclusive minimums and maximums (>|<) may not be combined "
            f"with their Inclusive counterparts (>=|<=). Got: {selector}."
        )
    return _ASSERTION_TRUTH_TABLE[selector]


class NumberAssertionsSelector(NamedTuple):
    exclusive_min: bool
    inclusive_min: bool
    exclusive_max: bool
    inclusive_max: bool
    has_mul: bool


_NT = TypeVar("_NT", bound=numbers.Number)


class AbstractNumberAssertion(assertions.AbstractAssertions[_NT]):
    selector: NumberAssertionsSelector

    __slots__ = (
        "max",
        "min",
        "mul",
    )

    def __repr__(self):
        return (
            f"<{self.__class__.__name__}("
            f"min={self.min!r}, max={self.max!r}, mul={self.mul!r})>"
        )

    def __init__(
        self,
        *,
        min: numbers.Number = None,
        max: numbers.Number = None,
        mul: numbers.Number = None,
    ):
        self.min = min
        self.max = max
        self.mul = mul
        self._check_syntax()
        super().__init__()

    def _check_syntax(self):
        if None in {self.min, self.max}:
            return
        if self.min == self.max:
            raise error.ConstraintSyntaxError(
                "Minimum must not be equal to maximum.",
            )


class MulOfAssertion(AbstractNumberAssertion[_NT]):
    selector = NumberAssertionsSelector(
        exclusive_min=False,
        inclusive_min=False,
        exclusive_max=False,
        inclusive_max=False,
        has_mul=True,
    )

    def _get_closure(self) -> assertions.AssertionProtocol[_NT]:
        def mul_of_assertion(val: numbers.Number, *, __mul=self.mul) -> bool:
            return val % __mul == 0

        return mul_of_assertion


class InclusiveMaxAssertion(AbstractNumberAssertion):
    selector = NumberAssertionsSelector(
        exclusive_min=False,
        inclusive_min=False,
        exclusive_max=False,
        inclusive_max=True,
        has_mul=False,
    )

    def _get_closure(self) -> assertions.AssertionProtocol[_NT]:
        def inclusive_max_assertion(val: numbers.Number, *, __max=self.max) -> bool:
            return val <= __max

        return inclusive_max_assertion


class InclusiveMaxAndMulOfAssertion(AbstractNumberAssertion):
    selector = NumberAssertionsSelector(
        exclusive_min=False,
        inclusive_min=False,
        exclusive_max=False,
        inclusive_max=True,
        has_mul=True,
    )

    def _get_closure(self) -> assertions.AssertionProtocol[_NT]:
        def inclusive_max_and_mul_assertion(
            val: numbers.Number, *, __max=self.max, __mul=self.mul
        ) -> bool:
            return val <= __max and val % __mul

        return inclusive_max_and_mul_assertion


class ExclusiveMaxAssertion(AbstractNumberAssertion):
    selector = NumberAssertionsSelector(
        exclusive_min=False,
        inclusive_min=False,
        exclusive_max=True,
        inclusive_max=False,
        has_mul=False,
    )

    def _get_closure(self) -> assertions.AssertionProtocol[_NT]:
        def exclusive_max_assertion(val: numbers.Number, *, __max=self.max) -> bool:
            return val < __max

        return exclusive_max_assertion


class ExclusiveMaxAndMulOfAssertion(AbstractNumberAssertion):
    selector = NumberAssertionsSelector(
        exclusive_min=False,
        inclusive_min=False,
        exclusive_max=True,
        inclusive_max=False,
        has_mul=True,
    )

    def _get_closure(self) -> assertions.AssertionProtocol[_NT]:
        def exclusive_max_and_mul_assertion(
            val: numbers.Number, *, __max=self.max, __mul=self.mul
        ) -> bool:
            return val < __max and val % __mul

        return exclusive_max_and_mul_assertion


class InclusiveMinAssertion(AbstractNumberAssertion):
    selector = NumberAssertionsSelector(
        exclusive_min=False,
        inclusive_min=True,
        exclusive_max=False,
        inclusive_max=False,
        has_mul=False,
    )

    def _get_closure(self) -> assertions.AssertionProtocol[_NT]:
        def inclusive_min_assertion(val: numbers.Number, *, __min=self.min) -> bool:
            return val >= __min

        return inclusive_min_assertion


class InclusiveMinAndMulOfAssertion(AbstractNumberAssertion):
    selector = NumberAssertionsSelector(
        exclusive_min=False,
        inclusive_min=True,
        exclusive_max=False,
        inclusive_max=False,
        has_mul=True,
    )

    def _get_closure(self) -> assertions.AssertionProtocol[_NT]:
        def inclusive_min_and_mul_assertion(
            val: numbers.Number, *, __min=self.min, __mul=self.mul
        ) -> bool:
            return val <= __min and val % __mul

        return inclusive_min_and_mul_assertion


class ExclusiveMinAssertion(AbstractNumberAssertion):
    selector = NumberAssertionsSelector(
        exclusive_min=True,
        inclusive_min=False,
        exclusive_max=False,
        inclusive_max=False,
        has_mul=False,
    )

    def _get_closure(self) -> assertions.AssertionProtocol[_NT]:
        def exclusive_min_assertion(val: numbers.Number, *, __min=self.min) -> bool:
            return val > __min

        return exclusive_min_assertion


class ExclusiveMinAndMulOfAssertion(AbstractNumberAssertion):
    selector = NumberAssertionsSelector(
        exclusive_min=True,
        inclusive_min=False,
        exclusive_max=False,
        inclusive_max=False,
        has_mul=True,
    )

    def _get_closure(self) -> assertions.AssertionProtocol[_NT]:
        def exclusive_min_and_mul_assertion(
            val: numbers.Number, *, __min=self.min, __mul=self.mul
        ) -> bool:
            return val <= __min and val % __mul

        return exclusive_min_and_mul_assertion


class InclusiveRangeAssertion(AbstractNumberAssertion):
    selector = NumberAssertionsSelector(
        exclusive_min=False,
        inclusive_min=True,
        exclusive_max=False,
        inclusive_max=True,
        has_mul=False,
    )

    def _get_closure(self) -> assertions.AssertionProtocol[_NT]:
        def inclusive_range_assertion(
            val: numbers.Number, *, __min=self.min, __max=self.max
        ) -> bool:
            return __min <= val <= __max

        return inclusive_range_assertion


class InclusiveRangeAndMulOfAssertion(AbstractNumberAssertion):
    selector = NumberAssertionsSelector(
        exclusive_min=False,
        inclusive_min=True,
        exclusive_max=False,
        inclusive_max=True,
        has_mul=True,
    )

    def _get_closure(self) -> assertions.AssertionProtocol[_NT]:
        def inclusive_range_and_mul_assertion(
            val: numbers.Number, *, __min=self.min, __max=self.max, __mul=self.mul
        ) -> bool:
            return __min <= val <= __max and val % __mul == 0

        return inclusive_range_and_mul_assertion


class RightInclusiveRangeAssertion(AbstractNumberAssertion):
    selector = NumberAssertionsSelector(
        exclusive_min=True,
        inclusive_min=False,
        exclusive_max=False,
        inclusive_max=True,
        has_mul=False,
    )

    def _get_closure(self) -> assertions.AssertionProtocol[_NT]:
        def right_inclusive_range_assertion(
            val: numbers.Number, *, __min=self.min, __max=self.max
        ) -> bool:
            return __min < val <= __max

        return right_inclusive_range_assertion


class RightInclusiveRangeAndMulOfAssertion(AbstractNumberAssertion):
    selector = NumberAssertionsSelector(
        exclusive_min=True,
        inclusive_min=False,
        exclusive_max=False,
        inclusive_max=True,
        has_mul=True,
    )

    def _get_closure(self) -> assertions.AssertionProtocol[_NT]:
        def inclusive_range_and_mul_assertion(
            val: numbers.Number, *, __min=self.min, __max=self.max, __mul=self.mul
        ) -> bool:
            return __min < val <= __max and val % __mul == 0

        return inclusive_range_and_mul_assertion


class LeftInclusiveRangeAssertion(AbstractNumberAssertion):
    selector = NumberAssertionsSelector(
        exclusive_min=False,
        inclusive_min=True,
        exclusive_max=True,
        inclusive_max=False,
        has_mul=False,
    )

    def _get_closure(self) -> assertions.AssertionProtocol[_NT]:
        def right_inclusive_range_and_mul_assertion(
            val: numbers.Number, *, __min=self.min, __max=self.max
        ) -> bool:
            return __min <= val < __max

        return right_inclusive_range_and_mul_assertion


class LeftInclusiveRangeAndMulOfAssertion(AbstractNumberAssertion):
    selector = NumberAssertionsSelector(
        exclusive_min=False,
        inclusive_min=True,
        exclusive_max=True,
        inclusive_max=False,
        has_mul=True,
    )

    def _get_closure(self) -> assertions.AssertionProtocol[_NT]:
        def left_inclusive_range_and_mul_assertion(
            val: numbers.Number, *, __min=self.min, __max=self.max, __mul=self.mul
        ) -> bool:
            return __min <= val < __max and val % __mul == 0

        return left_inclusive_range_and_mul_assertion


class ExclusiveRangeAssertion(AbstractNumberAssertion):
    selector = NumberAssertionsSelector(
        exclusive_min=True,
        inclusive_min=False,
        exclusive_max=True,
        inclusive_max=False,
        has_mul=False,
    )

    def _get_closure(self) -> assertions.AssertionProtocol[_NT]:
        def exclusive_range_and_mul_assertion(
            val: numbers.Number, *, __min=self.min, __max=self.max
        ) -> bool:
            return __min < val < __max

        return exclusive_range_and_mul_assertion


class ExclusiveRangeAndMulOfAssertion(AbstractNumberAssertion):
    selector = NumberAssertionsSelector(
        exclusive_min=False,
        inclusive_min=True,
        exclusive_max=True,
        inclusive_max=False,
        has_mul=True,
    )

    def _get_closure(self) -> assertions.AssertionProtocol[_NT]:
        def exclusive_range_and_mul_assertion(
            val: numbers.Number, *, __min=self.min, __max=self.max, __mul=self.mul
        ) -> bool:
            return __min < val < __max and val % __mul == 0

        return exclusive_range_and_mul_assertion


_ASSERTION_TRUTH_TABLE: dict[
    NumberAssertionsSelector, type[AbstractNumberAssertion]
] = {
    MulOfAssertion.selector: MulOfAssertion,
    InclusiveMaxAssertion.selector: InclusiveMaxAssertion,
    InclusiveMaxAndMulOfAssertion.selector: InclusiveMaxAndMulOfAssertion,
    ExclusiveMaxAssertion.selector: ExclusiveMaxAssertion,
    InclusiveMinAssertion.selector: InclusiveMinAssertion,
    InclusiveMinAndMulOfAssertion.selector: InclusiveMinAndMulOfAssertion,
    InclusiveRangeAssertion.selector: InclusiveRangeAssertion,
    InclusiveRangeAndMulOfAssertion.selector: InclusiveRangeAndMulOfAssertion,
    LeftInclusiveRangeAssertion.selector: LeftInclusiveRangeAssertion,
    LeftInclusiveRangeAndMulOfAssertion.selector: LeftInclusiveRangeAndMulOfAssertion,
    ExclusiveMinAssertion.selector: ExclusiveMinAssertion,
    ExclusiveMinAndMulOfAssertion.selector: ExclusiveMinAndMulOfAssertion,
    RightInclusiveRangeAssertion.selector: RightInclusiveRangeAssertion,
    RightInclusiveRangeAndMulOfAssertion.selector: RightInclusiveRangeAndMulOfAssertion,
    ExclusiveRangeAssertion.selector: ExclusiveRangeAssertion,
    ExclusiveRangeAndMulOfAssertion.selector: ExclusiveRangeAndMulOfAssertion,
}


# Methodology:
# #> import itertools
# #> options = (True,True,True,True,True, False,False,False,False,False,)
# #> combos = sorted(set(itertools.permutations(options, len(options)//2), reversed=True)
# #> illegal = [c for c in combos if (c[0] and c[1] or c[2] and c[3])]
_ILLEGAL_COMBINATIONS = frozenset(
    (
        (True, True, True, True, True),
        (True, True, True, True, False),
        (True, True, True, False, True),
        (True, True, True, False, False),
        (True, True, False, True, True),
        (True, True, False, True, False),
        (True, True, False, False, True),
        (True, True, False, False, False),
        (True, False, True, True, True),
        (True, False, True, True, False),
        (False, True, True, True, True),
        (False, True, True, True, False),
        (False, False, True, True, True),
        (False, False, True, True, False),
    )
)
