from typing import TypeVar, Generic

__all__ = (
    "ReadOnly",
    "Strict",
    "StrictStrT",
    "WriteOnly",
)

T = TypeVar("T")


class ReadOnly(Generic[T]):
    """A type annotation to indicate a field is meant to be read-only."""

    pass


class WriteOnly(Generic[T]):
    """A type annotation to indicate a field is meant to be write-only."""

    pass


_T = TypeVar("_T")


class Strict(Generic[_T]):
    pass


StrictStrT = Strict[str]
