from typing import TypeVar, Generic

from typic.types.frozendict import FrozenDict as _FrozenDict

__all__ = (
    "FrozenDict",
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


KT = TypeVar("KT")
VT = TypeVar("VT")


class FrozenDict(Generic[KT, VT], _FrozenDict):
    ...


FrozenDict.__doc__ = _FrozenDict.__doc__
FrozenDict.__module__ = _FrozenDict.__module__
