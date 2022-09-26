from __future__ import annotations

import copy
import inspect
from typing import Generic, Hashable, Iterable, Mapping, Protocol, TypeVar, overload

from typic.checks import ishashable
from typic.util import cached_property

__all__ = ("FrozenDict", "freeze")

KT = TypeVar("KT")  # Key type.
VT = TypeVar("VT", covariant=True)  # Value type.


class FrozenDict(Generic[KT, VT], dict):
    """An immutable, hashable mapping.

    This inherits directly from the builtin :py:class:`dict`.

    Notes
    -----
    Because it must recursively freeze all nested items to ensure it is hashable,
    this data-structure is substantially slower on init than a native dict.

    This operation is highly optimized, but the recursive nature is still expensive.

    However, once initialized, it is equivalent in performance to a native dict in every
    other way. The recommended use-case for this object is for compile-time objects
    (such as configurations, dictionary-dispatching, etc.).

    Examples
    --------
    >>> import typic
    >>> fdict = typic.FrozenDict({"foo": ["bar"]})
    >>> typic.ishashable(fdict)
    True
    >>> fdict["foo"]
    ('bar',)
    >>> fdict.update(foo=["car"])
    Traceback (most recent call last):
    ...
    TypeError: attempting to mutate immutable type 'FrozenDict'
    >>> del fdict["foo"]
    Traceback (most recent call last):
    ...
    TypeError: attempting to mutate immutable type 'FrozenDict'
    >>> fdict.pop("foo")
    Traceback (most recent call last):
    ...
    TypeError: attempting to mutate immutable type 'FrozenDict'
    >>> fdict.clear()
    Traceback (most recent call last):
    ...
    TypeError: attempting to mutate immutable type 'FrozenDict'
    """

    _MSG = "attempting to mutate immutable type 'FrozenDict'"

    def __init__(
        self,
        __obj: Mapping | Iterable[tuple[str, HashableT]] = None,
        *,
        __hashgetter=ishashable,
        **kwargs,
    ):
        super().__init__(
            {
                x: y if __hashgetter(y) else freeze(y)
                for x, y in {**(dict(__obj or {})), **kwargs}.items()
            }
        )

    def __copy__(self) -> "FrozenDict":
        return self.__class__({**self})

    def __deepcopy__(self, memodict: dict = None) -> "FrozenDict":
        return self.__class__({x: copy.deepcopy(y, memodict) for x, y in self.items()})

    @cached_property
    def __hash(self) -> int:
        return hash(frozenset(self.items()))

    def __hash__(self) -> int:  # type: ignore
        return self.__hash

    def __setitem__(self, key, value):
        """Mutations are disallowed."""
        raise TypeError(self._MSG) from None

    def __delitem__(self, key):
        """Mutations are disallowed."""
        raise TypeError(self._MSG) from None

    def pop(self, k):
        """Mutations are disallowed."""
        raise TypeError(self._MSG) from None

    def popitem(self):
        """Mutations are disallowed."""
        raise TypeError(self._MSG) from None

    def clear(self):
        """Mutations are disallowed."""
        raise TypeError(self._MSG) from None

    def update(self, *args, **kwargs):
        """Mutations are disallowed."""
        raise TypeError(self._MSG) from None

    def setdefault(self, *args, **kwargs):
        """Mutations are disallowed."""
        raise TypeError(self._MSG) from None

    def mutate(self, other: Mapping = None, **kwargs) -> "FrozenDict":
        """Return a new :py:class:`FrozenDict` with changes merged in.

        Priority of keys is in inverse order, i.e.:
            1. `**kwargs`
            2. `other` mapping
            3. `self`, the object you're mutating.

        Examples
        --------
        >>> import typic
        >>> fdict = typic.FrozenDict(foo=["bar"])
        >>> fdict.mutate({"bazz": "buzz"}, bazz="blah")
        {'foo': ('bar',), 'bazz': 'blah'}
        """
        return self.__class__({**self, **(other or {}), **kwargs})


class Unhashable(Protocol):
    def __hash__(self) -> None:
        ...


UnhashableT = TypeVar("UnhashableT", bound=Unhashable)
HashableT = TypeVar("HashableT", bound=Hashable)
_VT = TypeVar("_VT")
_KT = TypeVar("_KT")


@overload
def freeze(o: HashableT | UnhashableT) -> HashableT:
    ...


@overload
def freeze(o: type[None]) -> None:
    ...


@overload
def freeze(o: set[_VT]) -> frozenset[_VT]:
    ...


@overload
def freeze(o: dict[_KT, _VT]) -> FrozenDict[_KT, _VT]:
    ...


@overload
def freeze(o: list[_VT]) -> tuple[_VT]:
    ...


def freeze(o, *, __hashgetter=ishashable):
    if o is None:
        return o

    if __hashgetter(o) or inspect.isclass(o) or inspect.isfunction(o):
        return o

    if isinstance(o, set):
        return frozenset(o)

    if isinstance(o, Mapping):
        return FrozenDict(
            {x: y if __hashgetter(y) else freeze(y) for x, y in o.items()}
        )

    return (*(x if __hashgetter(x) else freeze(x) for x in o),)
