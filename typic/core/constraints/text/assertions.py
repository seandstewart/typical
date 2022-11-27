from __future__ import annotations

import functools
import re
from typing import Any, NamedTuple, TypeVar, cast

from typic.core.constraints.core import assertions

__all__ = (
    "get_assertion_cls",
    "AbstractTextAssertion",
    "MaxAndPatternAssertion",
    "MinAndPatternAssertion",
    "MaxAssertion",
    "MinAssertion",
    "PatternAssertion",
    "RangeAssertion",
    "RangeAndPatternAssertion",
    "TextAssertionSelector",
)


@functools.lru_cache(maxsize=None)
def get_assertion_cls(
    *,
    has_min: bool,
    has_max: bool,
    has_regex: bool,
) -> type[AbstractTextAssertion] | None:
    selector = TextAssertionSelector(
        has_min=has_min,
        has_max=has_max,
        has_regex=has_regex,
    )
    if selector == (False, False, False):
        return None
    return _ASSERTION_TRUTH_TABLE[selector]


class TextAssertionSelector(NamedTuple):
    has_min: bool
    has_max: bool
    has_regex: bool


_TT = TypeVar("_TT", str, bytes, bytearray)


class AbstractTextAssertion(assertions.AbstractAssertions[_TT]):
    selector: TextAssertionSelector

    __slots__ = (
        "min_length",
        "max_length",
        "regex",
    )

    def __repr__(self):
        return (
            "<("
            f"{self.__class__.__name__} "
            f"min_length={self.min_length!r}, "
            f"max_length={self.max_length!r}, "
            f"regex={self.regex!r}"
            ")>"
        )

    def __init__(
        self,
        *,
        min_length: int = None,
        max_length: int = None,
        regex: re.Pattern = None,
    ):
        self.min_length = min_length
        self.max_length = max_length
        self.regex = regex
        super().__init__()


class RangeAndPatternAssertion(AbstractTextAssertion[_TT]):
    selector = TextAssertionSelector(has_min=True, has_max=True, has_regex=True)

    def _get_closure(self) -> assertions.AssertionProtocol[_TT]:
        def range_and_pattern_assertion(
            val: Any,
            *,
            __min=self.min_length,
            __max=self.max_length,
            __match=self.regex.match,
        ) -> bool:

            return __min <= len(val) <= __max and __match(val) is not None

        return cast(assertions.AssertionProtocol[_TT], range_and_pattern_assertion)


class MaxAndPatternAssertion(AbstractTextAssertion[_TT]):
    selector = TextAssertionSelector(has_min=False, has_max=True, has_regex=True)

    def _get_closure(self) -> assertions.AssertionProtocol[_TT]:
        def max_and_pattern_assertion(
            val: Any, *, __max=self.max_length, __match=self.regex.match
        ) -> bool:
            return len(val) <= __max and __match(val) is not None

        return cast(assertions.AssertionProtocol[_TT], max_and_pattern_assertion)


class MinAndPatternAssertion(AbstractTextAssertion[_TT]):
    selector = TextAssertionSelector(has_min=True, has_max=False, has_regex=True)

    def _get_closure(self) -> assertions.AssertionProtocol[_TT]:
        def min_and_pattern_assertion(
            val: Any, *, __min=self.min_length, __match=self.regex.match
        ) -> bool:
            return __min <= len(val) and __match(val) is not None

        return cast(assertions.AssertionProtocol[_TT], min_and_pattern_assertion)


class RangeAssertion(AbstractTextAssertion[_TT]):
    selector = TextAssertionSelector(has_min=True, has_max=True, has_regex=False)

    def _get_closure(self) -> assertions.AssertionProtocol[_TT]:
        def range_asseertion(
            val: Any, *, __min=self.min_length, __max=self.max_length
        ) -> bool:
            return __min <= len(val) <= __max

        return cast(assertions.AssertionProtocol[_TT], range_asseertion)


class MinAssertion(AbstractTextAssertion[_TT]):
    selector = TextAssertionSelector(
        has_min=True,
        has_max=False,
        has_regex=False,
    )

    def _get_closure(self) -> assertions.AssertionProtocol[_TT]:
        def min_assertion(val: Any, *, __min=self.min_length) -> bool:
            return __min <= len(val)

        return cast(assertions.AssertionProtocol[_TT], min_assertion)


class MaxAssertion(AbstractTextAssertion[_TT]):
    selector = TextAssertionSelector(
        has_min=False,
        has_max=True,
        has_regex=False,
    )

    def _get_closure(self) -> assertions.AssertionProtocol[_TT]:
        def max_assertion(val: Any, *, __max=self.max_length) -> bool:
            return len(val) <= __max

        return cast(assertions.AssertionProtocol[_TT], max_assertion)


class PatternAssertion(AbstractTextAssertion[_TT]):
    selector = TextAssertionSelector(
        has_min=False,
        has_max=False,
        has_regex=True,
    )

    def _get_closure(self) -> assertions.AssertionProtocol[_TT]:
        def pattern_assertion(val: Any, *, __match=self.regex.match) -> bool:
            return __match(val) is not None

        return cast(assertions.AssertionProtocol[_TT], pattern_assertion)


_ASSERTION_TRUTH_TABLE: dict[TextAssertionSelector, type[AbstractTextAssertion]] = {
    RangeAndPatternAssertion.selector: RangeAndPatternAssertion,
    MaxAndPatternAssertion.selector: MaxAndPatternAssertion,
    MinAndPatternAssertion.selector: MinAndPatternAssertion,
    RangeAssertion.selector: RangeAssertion,
    MinAssertion.selector: MinAssertion,
    MaxAssertion.selector: MaxAssertion,
    PatternAssertion.selector: PatternAssertion,
}
