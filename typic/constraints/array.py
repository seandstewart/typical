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
    TYPE_CHECKING,
)

from typic import gen, checks, util
from typic.types.frozendict import freeze
from .common import BaseConstraints, ContextT, ChecksT

if TYPE_CHECKING:  # pragma: nocover
    from typic.constraints.factory import ConstraintsT  # noqa: F401

Array = Union[FrozenSet, Set, List, Tuple]
"""The supported builtin types for defining restricted array-types."""


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
    return hash(freeze(obj))


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


@util.slotted
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
    values: Optional["ConstraintsT"] = None
    """The constraints for which the items in the array must adhere.

    This can be a single type-constraint, or a tuple of multiple constraints.
    """

    def _build_validator(self, func: gen.Block) -> Tuple[ChecksT, ContextT]:
        # No need to sanity check the config.
        # Build the code.
        # Only make it unique if we have to. This preserves order as well.
        if self.unique is True and util.origin(self.type) not in {set, frozenset}:
            func.l(f"{self.VALUE} = __unique({self.VALUE})", __unique=unique)
        # Only get the size if we have to.
        if {self.max_items, self.min_items} != {None, None}:
            func.l(f"size = len({self.VALUE})")
        # Get the validation checks and context
        asserts: List[str] = []
        context: Dict[str, Any] = {}
        if self.min_items is not None:
            asserts.append(f"size >= {self.min_items}")
        if self.max_items is not None:
            asserts.append(f"size <= {self.max_items}")
        # Validate the items if necessary.
        if self.values:
            o = util.origin(self.type)
            itval = "__item_validator"
            ctx = {
                itval: self.values.validate,
                o.__name__: o,
                "_lazy_repr": util.collectionrepr,
            }
            r = "i" if issubclass(self.type, Sequence) else "x"
            field = f"_lazy_repr({self.FNAME}, {r})"
            func.l(
                f"{self.VALUE} = "
                f"{o.__name__}("
                f"({itval}(x, field={field}) for i, x in enumerate({self.VALUE}))"
                f")",
                **ctx,
            )
        return asserts, context

    def for_schema(self, *, with_type: bool = False) -> dict:
        schema: Dict[str, Any] = dict(
            title=self.name,
            minItems=self.min_items,
            maxItems=self.max_items,
            uniqueItems=self.unique,
            items=self.values.for_schema(with_type=True) if self.values else None,
        )
        if with_type:
            schema["type"] = "array"
        return {x: y for x, y in schema.items() if y is not None}


@util.slotted
@dataclasses.dataclass(frozen=True, repr=False)
class ListContraints(ArrayConstraints):
    """Specific constraints pertaining to a :py:class:`list`."""

    type: ClassVar[Type[list]] = list


@util.slotted
@dataclasses.dataclass(frozen=True, repr=False)
class TupleContraints(ArrayConstraints):
    """Specific constraints pertaining to a :py:class:`tuple`."""

    type: ClassVar[Type[tuple]] = tuple


@util.slotted
@dataclasses.dataclass(frozen=True, repr=False)
class SetContraints(ArrayConstraints):
    """Specific constraints pertaining to a :py:class:`set`."""

    type: ClassVar[Type[set]] = set
    unique: bool = True


@util.slotted
@dataclasses.dataclass(frozen=True, repr=False)
class FrozenSetConstraints(ArrayConstraints):
    """Specific constraints pertaining to a :py:class:`frozenset`."""

    type: ClassVar[Type[frozenset]] = frozenset
    unique: bool = True
