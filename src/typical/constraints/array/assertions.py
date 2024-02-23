from __future__ import annotations

import functools
from typing import Any, NamedTuple, Sized, TypeVar, cast

from typical.constraints.core import assertions

__all__ = (
    "get_assertion_cls",
    "AbstractArrayAssertion",
    "ItemRangeAssertion",
    "MinItemsAssertion",
    "MaxItemsAssertion",
)


@functools.lru_cache(maxsize=None)
def get_assertion_cls(
    *,
    has_min: bool,
    has_max: bool,
) -> type[AbstractArrayAssertion] | None:
    selector = ArrayAssertionSelector(has_min=has_min, has_max=has_max)
    if selector == (False, False):
        return None
    return _ASSERTION_TRUTH_TABLE[selector]


class ArrayAssertionSelector(NamedTuple):
    has_min: bool
    has_max: bool


_AT = TypeVar("_AT", bound=Sized)


class AbstractArrayAssertion(assertions.AbstractAssertions[_AT]):
    selector: ArrayAssertionSelector

    __slots__ = (
        "min_items",
        "max_items",
    )

    def __repr__(self):
        return (
            f"<({self.__class__.__name__} "
            f"min_items={self.min_items!r}, max_items={self.max_items!r})>"
        )

    def __init__(
        self,
        *,
        min_items: int = None,
        max_items: int = None,
    ):
        self.min_items = min_items
        self.max_items = max_items
        super().__init__()


class ItemRangeAssertion(AbstractArrayAssertion):
    selector = ArrayAssertionSelector(has_min=True, has_max=True)

    def _get_closure(self) -> assertions.AssertionProtocol[_AT]:
        def item_range_assertion(
            val: Any, *, __min_items=self.min_items, __max_items=self.max_items
        ) -> bool:
            return __min_items <= len(val) <= __max_items

        return cast(assertions.AssertionProtocol[_AT], item_range_assertion)


class MinItemsAssertion(AbstractArrayAssertion):
    selector = ArrayAssertionSelector(has_min=True, has_max=False)

    def _get_closure(self) -> assertions.AssertionProtocol[_AT]:
        def min_items_assertion(val: Any, *, __min_items=self.min_items) -> bool:
            return __min_items <= len(val)

        return cast(assertions.AssertionProtocol[_AT], min_items_assertion)


class MaxItemsAssertion(AbstractArrayAssertion):
    selector = ArrayAssertionSelector(has_min=False, has_max=True)

    def _get_closure(self) -> assertions.AssertionProtocol[_AT]:
        def max_items_assertion(val: Any, *, __max_items=self.max_items) -> bool:
            return len(val) <= __max_items

        return cast(assertions.AssertionProtocol[_AT], max_items_assertion)


_ASSERTION_TRUTH_TABLE: dict[ArrayAssertionSelector, type[AbstractArrayAssertion]] = {
    ItemRangeAssertion.selector: ItemRangeAssertion,
    MinItemsAssertion.selector: MinItemsAssertion,
    MaxItemsAssertion.selector: MaxItemsAssertion,
}
