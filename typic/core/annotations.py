from typing import Any, Type, TypeVar, Union

from typic.compat import Generic, Literal

AnyOrTypeT = Union[Type, Any]
TrueOrFalseT = Literal[True, False]
ObjectT = TypeVar("ObjectT")
"""A generic alias for an object."""
OriginT = TypeVar("OriginT")
"""A type alias for an instance of the type associated to a Coercer."""

T = TypeVar("T")


class ReadOnly(Generic[T]):
    """A type annotation to indicate a field is meant to be read-only."""

    pass


class WriteOnly(Generic[T]):
    """A type annotation to indicate a field is meant to be write-only."""

    pass
