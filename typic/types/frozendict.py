#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import copy
from operator import attrgetter
from typing import Union, Tuple, List, Any, TypeVar, Mapping, Generic
from collections.abc import Hashable

from typic.util import cached_property

__all__ = ("FrozenDict",)

KT = TypeVar("KT")  # Key type.
VT = TypeVar("VT", covariant=True)  # Value type.

_hashgetter = attrgetter("__hash__")


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

    _MSG = f"attempting to mutate immutable type 'FrozenDict'"

    def __init__(
        self, obj: Union[Mapping, List[Tuple[str, Hashable]]] = None, **kwargs
    ):
        super().__init__(
            {x: self._freeze(y) for x, y in {**(dict(obj or {})), **kwargs}.items()}
        )

    def __copy__(self) -> "FrozenDict":
        return type(self)({**self})

    def __deepcopy__(self, memodict: dict = None) -> "FrozenDict":
        return type(self)({x: copy.deepcopy(y, memodict) for x, y in self.items()})

    @classmethod
    def _freeze(
        cls, o: Any, *, __hashgetter=_hashgetter
    ) -> Union["FrozenDict", Hashable]:
        if __hashgetter(o):
            return o

        if isinstance(o, Mapping):
            return cls({x: cls._freeze(y) for x, y in o.items()})

        gen = (cls._freeze(x) for x in o)

        if isinstance(o, set):
            return frozenset(gen)

        return (*gen,)

    @cached_property
    def __hash(self) -> int:
        return hash((*self.items(),))

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
            1. ``**kwargs``
            2. ``other`` mapping
            3. ``self``, the object you're mutating.

        Examples
        --------
        >>> import typic
        >>> fdict = typic.FrozenDict(foo=["bar"])
        >>> fdict.mutate({"bazz": "buzz"}, bazz="blah")
        {'foo': ('bar',), 'bazz': 'blah'}
        """
        return type(self)({**self, **(other or {}), **kwargs})
