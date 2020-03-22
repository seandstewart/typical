import dataclasses
from typing import (
    Union,
    FrozenSet,
    Set,
    List,
    Tuple,
    ClassVar,
    Type,
    Optional,
    Dict,
    Any,
    TYPE_CHECKING,
)

from .builder import _build_validator
from ..common import BaseConstraints

if TYPE_CHECKING:
    from ..factory import ConstraintsT  # noqa: F401

Array = Union[FrozenSet, Set, List, Tuple]
"""The supported builtin types for defining restricted array-types."""


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
    builder = _build_validator
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

    def for_schema(self, *, with_type: bool = False) -> dict:
        schema: Dict[str, Any] = dict(
            minItems=self.min_items,
            maxItems=self.max_items,
            uniqueItems=self.unique,
            items=self.values.for_schema(with_type=True) if self.values else None,
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
