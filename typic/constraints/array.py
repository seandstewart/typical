#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import dataclasses
from typing import (
    Type,
    ClassVar,
    Tuple,
    Sequence,
    Dict,
    List,
    Any,
    Iterator,
    Union,
    Optional,
    Hashable,
    Set,
    FrozenSet,
)

from typic import gen, checks, util
from typic.types.frozendict import FrozenDict
from .common import BaseConstraints, Context, Checks
from .error import ConstraintValueError, raise_exc

Array = Union[FrozenSet, Set, List, Tuple]
"""The supported builtin types for defining restricted array-types."""


def _validate_items_multi(
    constraints: Dict[Type, BaseConstraints], val: Iterator[Any]
) -> Iterator[Any]:
    return (
        constraints[type(x)].validate(x)
        for x in val
        if type(x) in constraints
        or raise_exc(
            ConstraintValueError(f"{x!r} is not one of type {(*constraints,)}")
        )
    )


def _validate_items(constraints: BaseConstraints, val: Iterator[Any]) -> Iterator[Any]:
    return (constraints.validate(x) for x in val)


def unique_fast(
    seq: Sequence, *, ret_type: Type[Union[list, tuple]] = list
) -> Sequence:
    """Fastest order-preserving method for (hashable) uniques in Python >= 3.6.

    Notes
    -----
    Values of seq must be hashable!

    See Also
    --------
    `Uniquify List in Python 3.6 <https://www.peterbe.com/plog/fastest-way-to-uniquify-a-list-in-python-3.6>`_
    """
    return ret_type(dict.fromkeys(seq))


def unique_slow(
    seq: Sequence, *, ret_type: Type[Union[list, tuple]] = list
) -> Sequence:
    """Fastest order-preserving method for (unhashable) uniques in Python >= 3.6.

    See Also
    --------
    `Uniquify List in Python 3.6 <https://www.peterbe.com/plog/fastest-way-to-uniquify-a-list-in-python-3.6>`_
    """
    seen: Set[Hashable] = set()
    return ret_type(_unique_slow(seq, seen))


def _get_hash(obj: Any):
    if checks.ishashable(obj):
        return hash(obj)
    if dataclasses.is_dataclass(obj):
        obj = dataclasses.asdict(obj)
    return hash(FrozenDict._freeze(obj))


def _unique_slow(seq: Sequence, seen: set) -> Iterator[Any]:
    add = seen.add
    for x in seq:
        h = _get_hash(x)
        if h in seen:
            continue
        add(h)
        yield x


def unique(seq: Sequence, *, ret_type: Type[Union[list, tuple]] = list) -> Sequence:
    """Fastest, order-preserving method for uniques in Python >= 3.6.

    See Also
    --------
    `Uniquify List in Python 3.6 <https://www.peterbe.com/plog/fastest-way-to-uniquify-a-list-in-python-3.6>`_
    """
    try:
        return unique_fast(seq, ret_type=ret_type)
    except TypeError:
        return unique_slow(seq, ret_type=ret_type)


ItemConstraints = Union[BaseConstraints, Tuple[BaseConstraints]]
"""Constraints for the items present in the constrained array.

May be either a single constraint or a tuple of constraints.
"""


@dataclasses.dataclass(frozen=True, repr=False)
class ArrayConstraints(BaseConstraints):
    """Specific constraints pertaining to a sized, array-like type.

    These constraints are meant to align closely to JSON Schema type constraints.

    Notes
    -----
    Doesn't support mappings, but could be updated to do so.
    """

    type: ClassVar[Type[Array]]
    """The type of array the input should be."""
    min_items: Optional[int] = None
    """The minimum number of items which must be present in the array."""
    max_items: Optional[int] = None
    """The maximum number of items which may be present in the array."""
    unique: Optional[bool] = None
    """Whether this array should only have unique items.

    Notes
    -----
    Rather than reject arrays which are not unique, we will simply make the array unique.
    """
    items: Optional[Union[BaseConstraints, Tuple[BaseConstraints, ...]]] = None
    """The constraints for which the items in the array must adhere.

    This can be a single type-constraint, or a tuple of multiple constraints.
    """

    def _build_validator(self, func: gen.Block) -> Tuple[Checks, Context]:
        # No need to sanity check the config.
        # Build the code.
        # Only make it unique if we have to. This preserves order as well.
        if self.unique is True and util.origin(self.type) not in {set, frozenset}:
            func.l("val = __unique(val)", __unique=unique)
        # Only get the size if we have to.
        if {self.max_items, self.min_items} != {None, None}:
            func.l("size = len(val)")
        # Get the validation checks and context
        asserts: List[str] = []
        context: Dict[str, Any] = {}
        if self.min_items is not None:
            asserts.append(f"size >= {self.min_items}")
        if self.max_items is not None:
            asserts.append(f"size <= {self.max_items}")
        # Validate the items if necessary.
        if self.items:
            func.l(
                f"val = {util.origin(self.type).__name__}(__validate(__item_c, val))"
            )
            if isinstance(self.items, tuple):
                func.namespace.update(
                    __validate=_validate_items_multi,
                    __item_c={x.type: x for x in self.items},
                )
            else:
                func.namespace.update(__validate=_validate_items, __item_c=self.items)
        return asserts, context

    def for_schema(self, *, with_type: bool = False) -> dict:
        items = None
        if self.items:
            items = (
                {"anyOf": [x.for_schema(with_type=True) for x in self.items]}
                if isinstance(self.items, tuple)
                else self.items.for_schema(with_type=True)
            )
        schema: Dict[str, Any] = dict(
            minItems=self.min_items,
            maxItems=self.max_items,
            uniqueItems=self.unique,
            items=items,
        )
        if with_type:
            schema["type"] = "array"
        return {x: y for x, y in schema.items() if y is not None}


@dataclasses.dataclass(frozen=True, repr=False)
class ListContraints(ArrayConstraints):
    """Specific constraints pertaining to a :py:class:`list`."""

    type: ClassVar[Type[list]] = list


@dataclasses.dataclass(frozen=True, repr=False)
class TupleContraints(ArrayConstraints):
    """Specific constraints pertaining to a :py:class:`tuple`."""

    type: ClassVar[Type[tuple]] = tuple


@dataclasses.dataclass(frozen=True, repr=False)
class SetContraints(ArrayConstraints):
    """Specific constraints pertaining to a :py:class:`set`."""

    type: ClassVar[Type[set]] = set
    unique: bool = True


@dataclasses.dataclass(frozen=True, repr=False)
class FrozenSetConstraints(ArrayConstraints):
    """Specific constraints pertaining to a :py:class:`frozenset`."""

    type: ClassVar[Type[frozenset]] = frozenset
    unique: bool = True
