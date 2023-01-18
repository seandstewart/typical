from __future__ import annotations

import functools
import re
from typing import Any, Mapping, NamedTuple, TypeVar, cast

from typical.core.constraints.core import assertions

__all__ = (
    "get_assertion_cls",
    "AbstractMappingAssertion",
    "ItemRangeAssertion",
    "MinItemsAssertion",
    "MaxItemsAssertion",
    "PatternAssertion",
    "ItemRangePatternAssertion",
    "MaxItemsPatternAssertion",
    "MinItemsPatternAssertion",
)


@functools.lru_cache(maxsize=None)
def get_assertion_cls(
    *,
    has_min: bool,
    has_max: bool,
    has_key_pattern: bool,
) -> type[AbstractMappingAssertion] | None:
    if not any((has_min, has_max, has_key_pattern)):
        return None
    # We can only check totality if there are defined keys...
    selector = MappingAssertionSelector(
        has_min=has_min,
        has_max=has_max,
        has_key_pattern=has_key_pattern,
    )
    return _ASSERTION_TRUTH_TABLE[selector]


class MappingAssertionSelector(NamedTuple):
    has_min: bool
    has_max: bool
    has_key_pattern: bool


_MT = TypeVar("_MT", bound=Mapping)


class AbstractMappingAssertion(assertions.AbstractAssertions[_MT]):
    selector: MappingAssertionSelector

    __slots__ = (
        "min_items",
        "max_items",
        "key_pattern",
    )

    def __repr__(self):
        return (
            "<("
            f"{self.__class__.__name__} "
            f"min_items={self.min_items!r}, "
            f"max_items={self.max_items!r}, "
            f"key_pattern={self.key_pattern.pattern!r}, "
            ")>"
        )

    def __init__(
        self,
        *,
        min_items: int = None,
        max_items: int = None,
        key_pattern: re.Pattern = None,
    ):
        self.min_items = min_items
        self.max_items = max_items
        self.key_pattern = key_pattern
        super().__init__()


class ItemRangePatternAssertion(AbstractMappingAssertion[_MT]):
    selector = MappingAssertionSelector(
        has_min=True, has_max=True, has_key_pattern=True
    )

    def _get_closure(self) -> assertions.AssertionProtocol[_MT]:
        def item_range_pattern_assertion(
            val: Any,
            *,
            __min_items=self.min_items,
            __max_items=self.max_items,
            __match=self.key_pattern.match,
        ) -> bool:
            return __min_items <= len(val) <= __max_items and not any(
                __match(k) is None for k in val
            )

        return cast(assertions.AssertionProtocol[_MT], item_range_pattern_assertion)


class MinItemsPatternAssertion(AbstractMappingAssertion[_MT]):
    selector = MappingAssertionSelector(
        has_min=True, has_max=False, has_key_pattern=True
    )

    def _get_closure(self) -> assertions.AssertionProtocol[_MT]:
        def min_items_pattern_assertion(
            val: Any,
            *,
            __min_items=self.min_items,
            __match=self.key_pattern.match,
        ) -> bool:
            return __min_items <= len(val) and not any(__match(k) is None for k in val)

        return cast(assertions.AssertionProtocol[_MT], min_items_pattern_assertion)


class MaxItemsPatternAssertion(AbstractMappingAssertion[_MT]):
    selector = MappingAssertionSelector(
        has_min=False, has_max=True, has_key_pattern=True
    )

    def _get_closure(self) -> assertions.AssertionProtocol[_MT]:
        def max_items_pattern_assertion(
            val: Any,
            *,
            __max_items=self.max_items,
            __match=self.key_pattern.match,
        ) -> bool:
            return len(val) <= __max_items and not any(__match(k) is None for k in val)

        return cast(assertions.AssertionProtocol[_MT], max_items_pattern_assertion)


class PatternAssertion(AbstractMappingAssertion[_MT]):
    selector = MappingAssertionSelector(
        has_min=False, has_max=False, has_key_pattern=True
    )

    def _get_closure(self) -> assertions.AssertionProtocol[_MT]:
        def pattern_assertion(
            val: Any,
            *,
            __match=self.key_pattern.match,
        ) -> bool:
            return not any(__match(k) is None for k in val)

        return cast(assertions.AssertionProtocol[_MT], pattern_assertion)


class ItemRangeAssertion(AbstractMappingAssertion[_MT]):
    selector = MappingAssertionSelector(
        has_min=True, has_max=True, has_key_pattern=False
    )

    def _get_closure(self) -> assertions.AssertionProtocol[_MT]:
        def item_range_assertion(
            val: Any,
            *,
            __min_items=self.min_items,
            __max_items=self.max_items,
        ) -> bool:
            return __min_items <= len(val) <= __max_items

        return cast(assertions.AssertionProtocol[_MT], item_range_assertion)


class MinItemsAssertion(AbstractMappingAssertion[_MT]):
    selector = MappingAssertionSelector(
        has_min=True, has_max=False, has_key_pattern=False
    )

    def _get_closure(self) -> assertions.AssertionProtocol[_MT]:
        def min_items_assertion(
            val: Any,
            *,
            __min_items=self.min_items,
        ) -> bool:
            return __min_items <= len(val)

        return cast(assertions.AssertionProtocol[_MT], min_items_assertion)


class MaxItemsAssertion(AbstractMappingAssertion[_MT]):
    selector = MappingAssertionSelector(
        has_min=False, has_max=True, has_key_pattern=False
    )

    def _get_closure(self) -> assertions.AssertionProtocol[_MT]:
        def max_items_assertion(
            val: Any,
            *,
            __max_items=self.max_items,
        ) -> bool:
            return len(val) <= __max_items

        return cast(assertions.AssertionProtocol[_MT], max_items_assertion)


_ASSERTION_TRUTH_TABLE: dict[
    MappingAssertionSelector, type[AbstractMappingAssertion]
] = {
    ItemRangeAssertion.selector: ItemRangeAssertion,
    MinItemsAssertion.selector: MinItemsAssertion,
    MaxItemsAssertion.selector: MaxItemsAssertion,
    ItemRangePatternAssertion.selector: ItemRangePatternAssertion,
    MinItemsPatternAssertion.selector: MinItemsPatternAssertion,
    MaxItemsPatternAssertion.selector: MaxItemsPatternAssertion,
    PatternAssertion.selector: PatternAssertion,
}
