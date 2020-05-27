from typing import Generic, TypeVar

from typic.types import frozendict

KT = TypeVar("KT")
VT = TypeVar("VT")


class FrozenDict(Generic[KT, VT], frozendict.FrozenDict):
    ...


FrozenDict.__doc__ = frozendict.FrozenDict.__doc__
FrozenDict.__module__ = frozendict.FrozenDict.__module__
FrozenDict.__name__ = frozendict.FrozenDict.__name__
FrozenDict.__qualname__ = frozendict.FrozenDict.__qualname__

setattr(frozendict, "FrozenDict", FrozenDict)
