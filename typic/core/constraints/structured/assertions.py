from __future__ import annotations

import functools
from typing import Any, Collection, Mapping, NamedTuple, TypeVar, cast

from typic.core.constraints.core import assertions

__all__ = (
    "get_assertion_cls",
    "AbstractStructuredObjectAssertion",
    "StructuredFieldsObjectAssertion",
    "StructuredFieldsTupleAssertion",
    "StructuredTupleAssertion",
)

from typic import checks


@functools.lru_cache(maxsize=None)
def get_assertion_cls(
    *,
    has_fields: bool,
    is_tuple: bool,
) -> type[AbstractStructuredObjectAssertion] | None:
    if {has_fields, is_tuple} == {False, False}:
        return None
    selector = StructuredObjectAssertionSelector(
        has_fields=has_fields,
        is_tuple=is_tuple,
    )
    return _ASSERTION_TRUTH_TABLE[selector]


_ST = TypeVar("_ST")
_NT = TypeVar("_NT", bound=NamedTuple)
_TT = TypeVar("_TT", bound=tuple)


class AbstractStructuredObjectAssertion(assertions.AbstractAssertions[_ST]):
    selector: StructuredObjectAssertionSelector

    __slots__ = ("fields", "size")

    def __repr__(self):
        return (
            "<("
            f"{self.__class__.__name__} "
            f"fields={self.fields!r}, "
            f"size={self.size!r}"
            ")>"
        )

    def __init__(self, *, fields: frozenset[str] | frozenset[int], size: int):
        self.fields = fields
        self.size = size
        super().__init__()


class StructuredObjectAssertionSelector(NamedTuple):
    has_fields: bool
    is_tuple: bool


class StructuredFieldsObjectAssertion(AbstractStructuredObjectAssertion[_ST]):
    selector = StructuredObjectAssertionSelector(has_fields=True, is_tuple=False)

    def _get_closure(self) -> assertions.AssertionProtocol[_ST]:
        def structured_fields_object_assertion(
            val: Mapping[str, Any] | Collection[tuple[str, Any]],
            *,
            __fields=self.fields,
            __ismappingtype=checks.ismappingtype,
            __iscollectiontype=checks.iscollectiontype,
        ) -> bool:
            cls = val.__class__
            if __ismappingtype(cls):
                return __fields <= val.keys()  # type: ignore
            if __iscollectiontype(cls) and len(val[0]) == 2:  # type: ignore[index]
                fields = {f for f, v in val}  # type: ignore[misc]
                return __fields <= fields
            return False

        return cast(
            assertions.AssertionProtocol[_ST], structured_fields_object_assertion
        )


class StructuredFieldsTupleAssertion(StructuredFieldsObjectAssertion[_NT]):
    selector = StructuredObjectAssertionSelector(has_fields=True, is_tuple=True)


class StructuredTupleAssertion(AbstractStructuredObjectAssertion[_TT]):
    selector = StructuredObjectAssertionSelector(has_fields=False, is_tuple=True)

    def _get_closure(self) -> assertions.AssertionProtocol[_TT]:
        def structured_tuple_assertion(
            val: Collection,
            *,
            __iscollectiontype=checks.iscollectiontype,
            __size=self.size,
        ) -> bool:
            if __iscollectiontype(val.__class__):
                return __size <= len(val)
            return False

        return cast(assertions.AssertionProtocol[_TT], structured_tuple_assertion)


_ASSERTION_TRUTH_TABLE: dict[
    StructuredObjectAssertionSelector, type[AbstractStructuredObjectAssertion]
] = {
    StructuredFieldsObjectAssertion.selector: StructuredFieldsObjectAssertion,
    StructuredFieldsTupleAssertion.selector: StructuredFieldsTupleAssertion,
    StructuredTupleAssertion.selector: StructuredTupleAssertion,
}
